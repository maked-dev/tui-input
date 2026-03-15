"""Textual companion app — pinned input bar at the bottom of a tmux split."""

from __future__ import annotations

import contextlib
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, TextArea

from tui_input import __version__
from tui_input.history import History
from tui_input.tmux import (
    cancel_copy_mode,
    pane_alive,
    pane_height,
    pane_pid,
    resize_pane,
    send_keys,
    send_raw,
    submit_to_pane,
    unset_hook,
)

if TYPE_CHECKING:
    from textual.events import Key
    from textual.timer import Timer

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

MIN_HEIGHT = 7
MAX_HEIGHT = 12
PROCESS_CHECK_INTERVAL = 0.3

# IME commit delay — short enough to be imperceptible, long enough for
# terminal IME to settle after a key event.
_IME_COMMIT_DELAY = 0.05

CSS_PATH = Path(__file__).parent / "companion.tcss"

# Rough bytes-per-token ratio used for the status bar estimate.
_BYTES_PER_TOKEN = 4

# ---------------------------------------------------------------------------
# Key mapping tables
#
# Each table maps a Textual key name to a value that determines how the
# key is forwarded to the agent pane.
# ---------------------------------------------------------------------------

# Keys that insert a newline (terminal-dependent names for Shift+Enter).
_NEWLINE_KEYS: frozenset[str] = frozenset(
    {
        "shift+enter",
        "shift+return",
        "alt+enter",
        "meta+enter",
        "ctrl+j",
    }
)

# Keys that are ALWAYS forwarded to the agent pane as raw bytes,
# regardless of whether the companion has text.
_ALWAYS_FORWARD_KEYS: dict[str, str] = {
    "ctrl+c": "\x03",
}

# Keys forwarded to the agent only when the companion is empty (raw bytes).
_EMPTY_FORWARD_RAW: dict[str, str] = {
    "escape": "\x1b",
    "ctrl+d": "\x04",
    "ctrl+l": "\x0c",
    "ctrl+z": "\x1a",
}

# Keys forwarded to the agent only when the companion is empty (tmux key names).
_EMPTY_FORWARD_NAMED: dict[str, str] = {
    "left": "Left",
    "right": "Right",
    "up": "Up",
    "down": "Down",
    "tab": "Tab",
    "shift+tab": "BTab",
}

# Known interactive shells — used by ``_is_shell`` to distinguish a shell
# wrapper from a directly-executed agent process.
_KNOWN_SHELLS: frozenset[str] = frozenset(
    {
        "zsh",
        "bash",
        "sh",
        "fish",
        "dash",
        "ksh",
        "tcsh",
        "csh",
    }
)


# ---------------------------------------------------------------------------
# Process inspection helpers
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Rough token estimate based on UTF-8 byte length."""
    if not text:
        return 0
    return max(1, len(text.encode("utf-8")) // _BYTES_PER_TOKEN)


def _has_children(pid: int) -> bool:
    """Return True if *pid* has any child processes (requires ``pgrep``)."""
    result = subprocess.run(
        ["pgrep", "-P", str(pid)],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _is_shell(pid: int) -> bool:
    """Return True if *pid* is a known interactive shell."""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True,
            text=True,
            check=True,
        )
        # Login shells are prefixed with "-" (e.g. "-zsh").
        comm = result.stdout.strip().lstrip("-")
        return comm in _KNOWN_SHELLS
    except subprocess.CalledProcessError:
        return False


# ---------------------------------------------------------------------------
# InputArea — custom TextArea with key forwarding
# ---------------------------------------------------------------------------


class InputArea(TextArea):
    """Custom TextArea that replaces the agent CLI's input area.

    Intercepts specific keys (Enter, Shift+Enter, Ctrl+C, …) and either
    forwards them to the agent pane or performs local actions (newline,
    send, history navigation).  All other keys are delegated to the
    parent ``TextArea``.
    """

    _pending_enter_timer: Timer | None = None

    # -- Timer management ----------------------------------------------------

    def _cancel_pending_enter(self) -> None:
        """Cancel any pending deferred Enter/newline timer."""
        if self._pending_enter_timer is not None:
            self._pending_enter_timer.stop()
            self._pending_enter_timer = None

    # -- Deferred actions (IME-safe) -----------------------------------------

    def _deferred_send(self) -> None:
        """Schedule ``_send`` after the IME commit delay."""

        def _callback() -> None:
            self._pending_enter_timer = None
            self._send()

        self._pending_enter_timer = self.set_timer(_IME_COMMIT_DELAY, _callback)

    def _deferred_newline(self) -> None:
        """Schedule newline insertion after the IME commit delay."""

        def _callback() -> None:
            self._pending_enter_timer = None
            self.insert("\n")

        self._pending_enter_timer = self.set_timer(_IME_COMMIT_DELAY, _callback)

    def _deferred_enter(self) -> None:
        """Schedule Enter action after the IME commit delay.

        After the delay: if empty, forward ``\\r`` to agent; otherwise send.
        """

        def _callback() -> None:
            self._pending_enter_timer = None
            if not self.text:
                self._forward_raw("\r")
            else:
                self._send()

        self._pending_enter_timer = self.set_timer(_IME_COMMIT_DELAY, _callback)

    # -- Text submission -----------------------------------------------------

    def _send(self) -> None:
        """Send text to the target pane and clear the editor."""
        app = self.app
        if not isinstance(app, CompanionApp):
            return
        text = self.text.strip()
        if not text:
            return
        try:
            submit_to_pane(app.target_pane, text)
        except Exception:
            app.bell()
            return
        app.history.add(text)
        self.text = ""
        if app.companion_pane:
            with contextlib.suppress(subprocess.CalledProcessError):
                resize_pane(app.companion_pane, MIN_HEIGHT)
        self._scroll_target_to_bottom()

    def _scroll_target_to_bottom(self) -> None:
        """Exit copy-mode on the target pane so it scrolls to the bottom."""
        if not isinstance(self.app, CompanionApp):
            return
        with contextlib.suppress(Exception):
            cancel_copy_mode(self.app.target_pane)

    # -- Key forwarding helpers ----------------------------------------------

    def _forward_raw(self, data: str) -> None:
        """Forward raw bytes to the agent pane."""
        if not isinstance(self.app, CompanionApp):
            return
        with contextlib.suppress(subprocess.CalledProcessError):
            send_raw(self.app.target_pane, data)

    def _forward_key(self, tmux_key: str) -> None:
        """Forward a named key to the agent pane via ``tmux send-keys``."""
        if not isinstance(self.app, CompanionApp):
            return
        with contextlib.suppress(subprocess.CalledProcessError):
            send_keys(self.app.target_pane, tmux_key)

    # -- Key event dispatch --------------------------------------------------

    async def _on_key(self, event: Key) -> None:
        """Handle all key input with contextual forwarding."""
        app = self.app
        is_empty = not self.text

        # --- Always forward to agent (e.g. Ctrl+C) ---
        if event.key in _ALWAYS_FORWARD_KEYS:
            self._cancel_pending_enter()
            event.prevent_default()
            event.stop()
            self._forward_raw(_ALWAYS_FORWARD_KEYS[event.key])
            return

        # --- Forward to agent when companion is empty (raw bytes) ---
        if is_empty and event.key in _EMPTY_FORWARD_RAW:
            self._cancel_pending_enter()
            event.prevent_default()
            event.stop()
            self._forward_raw(_EMPTY_FORWARD_RAW[event.key])
            return

        # --- Forward to agent when companion is empty (named keys) ---
        if is_empty and event.key in _EMPTY_FORWARD_NAMED:
            self._cancel_pending_enter()
            event.prevent_default()
            event.stop()
            self._forward_key(_EMPTY_FORWARD_NAMED[event.key])
            return

        # --- Escape with text: clear companion ---
        if event.key == "escape":
            self._cancel_pending_enter()
            event.prevent_default()
            event.stop()
            self.text = ""
            if isinstance(app, CompanionApp):
                app.history.reset_navigation()
            return

        # --- Newline insertion (Shift+Enter / Alt+Enter / Ctrl+J) ---
        if event.key in _NEWLINE_KEYS:
            self._cancel_pending_enter()
            event.prevent_default()
            event.stop()
            self._deferred_newline()
            return

        # --- Enter: deferred for IME composition ---
        if event.key == "enter":
            self._cancel_pending_enter()
            event.prevent_default()
            event.stop()
            self._deferred_enter()
            return

        # --- History navigation (Ctrl+Up/Down, empty companion only) ---
        if not isinstance(app, CompanionApp):
            await super()._on_key(event)
            return
        history = app.history

        if event.key == "ctrl+up" and is_empty:
            self._cancel_pending_enter()
            event.prevent_default()
            event.stop()
            prev = history.get_previous()
            if prev is not None:
                self.text = prev
                self.move_cursor_relative(rows=999, columns=999)
            return

        if event.key == "ctrl+down" and is_empty:
            self._cancel_pending_enter()
            event.prevent_default()
            event.stop()
            nxt = history.get_next()
            if nxt is not None:
                self.text = nxt
                self.move_cursor_relative(rows=999, columns=999)
            else:
                self.text = ""
            return

        # --- Everything else: let TextArea handle ---
        await super()._on_key(event)


# ---------------------------------------------------------------------------
# CompanionApp — Textual application
# ---------------------------------------------------------------------------


class CompanionApp(App[None]):
    """A companion input widget that sends text to a target tmux pane."""

    CSS_PATH: ClassVar[str | Path] = CSS_PATH

    def __init__(
        self,
        target_pane: str,
        companion_pane: str | None = None,
        target_pid: int | None = None,
    ) -> None:
        super().__init__()
        self.target_pane = target_pane
        self.companion_pane = companion_pane
        self.target_pid = target_pid
        self.history = History()

    def compose(self) -> ComposeResult:
        yield InputArea(id="editor")
        with Horizontal(id="statusbar"):
            yield Static(f"tui-input {__version__}", id="version")
            yield Static("0 chars · 0 bytes · ~0 tokens", id="stats")

    def on_mount(self) -> None:
        editor = self.query_one("#editor", InputArea)
        editor.show_line_numbers = False
        editor.soft_wrap = True
        editor.tab_behavior = "indent"
        self.set_interval(PROCESS_CHECK_INTERVAL, self._check_target_alive)

    def on_unmount(self) -> None:
        """Clean up tmux hook when companion exits."""
        if self.companion_pane:
            with contextlib.suppress(Exception):
                unset_hook("after-split-window", self.companion_pane)

    @on(TextArea.Changed)
    def _on_text_changed(self, event: TextArea.Changed) -> None:
        """Adjust pane height based on line count and update stats."""
        text = event.text_area.text

        # Resize companion pane (only expand, never shrink).
        line_count = text.count("\n") + 1 if text else 1
        # +2 accounts for editor chrome (border) and stats footer.
        target_height = max(MIN_HEIGHT, min(line_count + 2, MAX_HEIGHT))
        if self.companion_pane:
            with contextlib.suppress(subprocess.CalledProcessError):
                current = pane_height(self.companion_pane)
                if target_height > current:
                    resize_pane(self.companion_pane, target_height)

        # Update stats footer.
        chars = len(text)
        byte_count = len(text.encode("utf-8"))
        tokens = _estimate_tokens(text)
        stats = self.query_one("#stats", Static)
        stats.update(f"{chars} chars · {byte_count} bytes · ~{tokens} tokens")

    def _check_target_alive(self) -> None:
        """Check if the agent pane is still alive; exit if not.

        Two modes depending on what process owns the target pane:

        * **Shell mode** (inside-tmux): the pane runs a shell (zsh/bash)
          that spawned the agent as a child.  When the agent exits, the
          shell has no children → companion exits.
        * **Direct mode** (outside-tmux): the pane runs the agent
          directly (no shell wrapper).  We simply check if the pane
          process is still alive.
        """
        if not pane_alive(self.target_pane):
            self.exit()
            return
        if self.target_pid is None:
            return
        if _is_shell(self.target_pid):
            if not _has_children(self.target_pid):
                self.exit()
        else:
            try:
                os.kill(self.target_pid, 0)
            except ProcessLookupError:
                self.exit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_companion(target_pane: str) -> None:
    """Run the companion app targeting a specific tmux pane."""
    # Use TMUX_PANE env var to get the companion's own pane ID.
    # ``current_pane_id()`` uses ``tmux display-message -p`` which returns
    # the *selected* pane (the agent), not the pane we're running in.
    companion_pane = os.environ.get("TMUX_PANE")
    target_pid: int | None = None
    with contextlib.suppress(Exception):
        target_pid = pane_pid(target_pane)
    CompanionApp(
        target_pane=target_pane,
        companion_pane=companion_pane,
        target_pid=target_pid,
    ).run()
