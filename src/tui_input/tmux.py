"""Tmux utility functions for pane management and text pasting."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile


class TmuxNotInstalledError(RuntimeError):
    """Raised when tmux is not found on the system."""


class TmuxCommandError(RuntimeError):
    """Raised when a tmux subcommand fails with additional context."""


def ensure_tmux_installed() -> None:
    """Check that tmux is installed and raise a helpful error if not."""
    if shutil.which("tmux") is None:
        raise TmuxNotInstalledError(
            "tmux is required but not installed.\n"
            "Install it with:\n"
            "  macOS:  brew install tmux\n"
            "  Ubuntu: sudo apt install tmux\n"
            "  Fedora: sudo dnf install tmux"
        )


def in_tmux() -> bool:
    """Return True if the current process is running inside a tmux session."""
    return "TMUX" in os.environ


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_tmux(*args: str) -> str:
    """Run a tmux subcommand and return stripped stdout.

    Raises:
        TmuxCommandError: If the tmux command exits with a non-zero status.
    """
    try:
        result = subprocess.run(
            ["tmux", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        cmd_str = " ".join(["tmux", *args])
        stderr = (exc.stderr or "").strip()
        raise TmuxCommandError(f"tmux command failed: {cmd_str!r} — {stderr}") from exc
    return result.stdout.strip()


def _paste_via_buffer(pane_id: str, data: bytes, *, bracketed: bool = False) -> None:
    """Write *data* to a temp file, load it into a tmux buffer, and paste it.

    Args:
        pane_id: Target tmux pane.
        data: Raw bytes to paste.
        bracketed: If True, use bracketed-paste mode (``-p``).
    """
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        f.write(data)
        tmp_path = f.name
    try:
        _run_tmux("load-buffer", tmp_path)
        paste_args = ["paste-buffer", "-d", "-t", pane_id]
        if bracketed:
            paste_args.insert(1, "-p")
        _run_tmux(*paste_args)
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Public API — pane queries
# ---------------------------------------------------------------------------


def current_pane_id() -> str:
    """Return the pane ID (e.g. '%3') of the current tmux pane."""
    return _run_tmux("display-message", "-p", "#{pane_id}")


def pane_exists(pane_id: str) -> bool:
    """Check if a tmux pane still exists."""
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{pane_id}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return pane_id in result.stdout.splitlines()
    except subprocess.CalledProcessError:
        return False


def pane_pid(pane_id: str) -> int | None:
    """Return the PID of the process running in a tmux pane, or None."""
    try:
        result = _run_tmux("display-message", "-t", pane_id, "-p", "#{pane_pid}")
        return int(result)
    except (TmuxCommandError, ValueError):
        return None


def pane_alive(pane_id: str) -> bool:
    """Check if a tmux pane exists AND its process is still running.

    Returns False if the pane doesn't exist or its process has exited
    (even if the pane remains due to ``remain-on-exit``).
    """
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-t", pane_id, "-p", "#{pane_dead}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() != "1"
    except subprocess.CalledProcessError:
        return False


def pane_height(pane_id: str) -> int:
    """Return the height in lines of a tmux pane."""
    return int(_run_tmux("display-message", "-t", pane_id, "-p", "#{pane_height}"))


def pane_width(pane_id: str) -> int:
    """Return the width in columns of a tmux pane."""
    return int(_run_tmux("display-message", "-t", pane_id, "-p", "#{pane_width}"))


# ---------------------------------------------------------------------------
# Public API — pane actions
# ---------------------------------------------------------------------------


def split_window(size: int, command: str | None = None) -> str:
    """Split the current pane vertically and return the new pane ID.

    Args:
        size: Height in lines for the new (bottom) pane.
        command: Optional shell command to run in the new pane.

    Returns:
        The pane ID of the newly created pane.
    """
    args = ["split-window", "-v", "-l", str(size), "-P", "-F", "#{pane_id}"]
    if command:
        args.append(command)
    return _run_tmux(*args)


def send_keys(pane_id: str, keys: str) -> None:
    """Send a named key (e.g. 'Enter', 'Escape', 'C-c') to a tmux pane."""
    _run_tmux("send-keys", "-t", pane_id, keys)


def send_raw(pane_id: str, data: str) -> None:
    """Send raw bytes to a tmux pane via load-buffer + paste-buffer.

    Unlike send_keys, this sends arbitrary data without key name interpretation.
    Useful for forwarding control characters (Ctrl+C = ``\\x03``, etc.).
    """
    _paste_via_buffer(pane_id, data.encode("utf-8"))


def paste_to_pane(pane_id: str, text: str) -> None:
    """Paste text into a tmux pane using bracketed paste for safe multi-line handling."""
    _paste_via_buffer(pane_id, text.encode("utf-8"), bracketed=True)


def submit_to_pane(pane_id: str, text: str) -> None:
    """Paste text into a pane, then send Enter separately.

    The text and the submit keystroke are sent as two distinct operations
    so that the target application (e.g. Claude Code) reliably treats
    Enter as a submit action rather than part of the pasted content.
    """
    _paste_via_buffer(pane_id, text.encode("utf-8"))
    _run_tmux("send-keys", "-t", pane_id, "Enter")


def resize_pane(pane_id: str, height: int) -> None:
    """Resize a tmux pane to the given height."""
    _run_tmux("resize-pane", "-t", pane_id, "-y", str(height))


def set_hook(hook_name: str, command: str, target: str) -> None:
    """Register a tmux hook at window scope."""
    _run_tmux("set-hook", "-w", "-t", target, hook_name, command)


def unset_hook(hook_name: str, target: str) -> None:
    """Remove a tmux hook at window scope."""
    _run_tmux("set-hook", "-u", "-w", "-t", target, hook_name)


def rejoin_companion(agent_pane: str, companion_pane: str, height: int) -> None:
    """Move companion pane below agent pane with join-pane."""
    _run_tmux("join-pane", "-v", "-s", companion_pane, "-t", agent_pane, "-l", str(height))


def cancel_copy_mode(pane_id: str) -> None:
    """Exit copy-mode on a pane so it scrolls to the bottom.

    If the pane is not in copy-mode, the enter/cancel sequence is harmless.
    """
    _run_tmux("copy-mode", "-t", pane_id)
    _run_tmux("send-keys", "-t", pane_id, "-X", "cancel")


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def create_session_with_split(
    session_name: str,
    main_command: str,
    companion_command: str,
    companion_height: int = 3,
) -> None:
    """Create a new tmux session with a vertical split.

    The main command runs in the top pane; the companion runs in the bottom.
    This function replaces the current process with ``tmux attach``.

    Args:
        session_name: Name for the tmux session.
        main_command: Shell command to run in the top pane.
        companion_command: Shell command to run in the bottom pane.
        companion_height: Height in lines for the bottom pane.
    """
    # Kill any stale session with the same name before creating a new one.
    subprocess.run(
        ["tmux", "kill-session", "-t", session_name],
        capture_output=True,
    )
    subprocess.run(
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            session_name,
            "-x",
            "200",
            "-y",
            "50",
            main_command,
        ],
        check=True,
    )
    # Grab the top pane's ID before splitting (works regardless of base-index).
    top_pane = (
        subprocess.run(
            ["tmux", "list-panes", "-t", f"{session_name}:", "-F", "#{pane_id}"],
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.strip()
        .splitlines()[0]
    )
    subprocess.run(
        [
            "tmux",
            "split-window",
            "-t",
            f"{session_name}:",
            "-v",
            "-l",
            str(companion_height),
            companion_command,
        ],
        check=True,
    )
    # Select the top pane so the user interacts with the agent.
    subprocess.run(["tmux", "select-pane", "-t", top_pane], check=True)
    # User-provided command is already validated by the CLI layer.
    os.execvp("tmux", ["tmux", "attach-session", "-t", session_name])  # noqa: S606
