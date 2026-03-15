"""Tmux environment setup — splits pane and launches companion + agent."""

from __future__ import annotations

import os
import shlex
import shutil
import sys

from tui_input.tmux import (
    create_session_with_split,
    current_pane_id,
    in_tmux,
    set_hook,
    split_window,
)

COMPANION_HEIGHT = 9
SESSION_NAME = "tui-input"


def launch(command: str) -> None:
    """Set up tmux split and launch the companion alongside the given command.

    If already inside tmux, splits the current pane.
    If outside tmux, creates a new session with the split.

    The current process is replaced by the agent command (top pane).
    """
    tui_input_bin = _find_tui_input_bin()
    companion_base = f"{tui_input_bin} --companion --target-pane"

    if in_tmux():
        _launch_inside_tmux(command, tui_input_bin, companion_base)
    else:
        _launch_outside_tmux(command, companion_base)


def _find_tui_input_bin() -> str:
    """Return a shell command that invokes tui-input via the current interpreter."""
    return f"{sys.executable} -m tui_input"


def _launch_inside_tmux(command: str, tui_input_bin: str, companion_base: str) -> None:
    """Split the current tmux pane and launch companion in the bottom."""
    top_pane = current_pane_id()
    companion_cmd = f"{companion_base} {top_pane}"

    # Split current pane: companion goes to the bottom.
    companion_pane = split_window(COMPANION_HEIGHT, companion_cmd)

    # Register hook to fix layout when agent pane is split.
    fix_layout_cmd = (
        f"run-shell '{tui_input_bin} --fix-layout"
        f" --agent-pane {top_pane} --companion-pane {companion_pane}'"
    )
    set_hook("after-split-window", fix_layout_cmd, target=top_pane)

    # Replace current process with the agent command.
    args = shlex.split(command)
    _validate_command(args[0])
    os.execvp(args[0], args)  # noqa: S606 — command is validated above


def _launch_outside_tmux(command: str, companion_base: str) -> None:
    """Create a new tmux session with agent + companion split."""
    # The companion command will resolve the target pane at startup.
    companion_cmd = (
        f"sleep 0.5 && TARGET=$(tmux list-panes -t {SESSION_NAME}: "
        f"-F '#{{pane_id}}' | head -1) && "
        f"{companion_base} $TARGET"
    )

    create_session_with_split(
        session_name=SESSION_NAME,
        main_command=command,
        companion_command=companion_cmd,
        companion_height=COMPANION_HEIGHT,
    )


def _validate_command(executable: str) -> None:
    """Verify that *executable* exists on PATH before ``execvp``.

    Raises:
        SystemExit: If the executable cannot be found.
    """
    if shutil.which(executable) is None:
        raise SystemExit(f"Error: command not found: {executable}")
