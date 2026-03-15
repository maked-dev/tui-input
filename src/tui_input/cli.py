"""CLI entry point for tui-input."""

from __future__ import annotations

import argparse
import sys

from tui_input import __version__


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the tui-input CLI."""
    parser = argparse.ArgumentParser(
        prog="tui-input",
        usage="%(prog)s <command> [args ...]",
        description=(
            "Pin a persistent input bar at the bottom of tmux.\n"
            "The command runs in the top pane; you type in the bottom."
        ),
        epilog=(
            "examples:\n"
            "  tui-input claude            Launch Claude Code with input bar\n"
            "  tui-input vim file.py       Launch Vim with input bar\n"
            "\n"
            "tip:\n"
            "  Register a shell alias to skip typing 'tui-input' every time:\n"
            "    echo \"alias claude='tui-input claude'\" >> ~/.zshrc"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        metavar="<command>",
        help="command to run in the top pane (e.g. claude, codex, vim)",
    )
    parser.add_argument(
        "--companion",
        action="store_true",
        help=argparse.SUPPRESS,  # Internal flag
    )
    parser.add_argument(
        "--target-pane",
        help=argparse.SUPPRESS,  # Internal flag
    )
    parser.add_argument(
        "--fix-layout",
        action="store_true",
        help=argparse.SUPPRESS,  # Internal flag
    )
    parser.add_argument(
        "--agent-pane",
        help=argparse.SUPPRESS,  # Internal flag
    )
    parser.add_argument(
        "--companion-pane",
        help=argparse.SUPPRESS,  # Internal flag
    )

    args = parser.parse_args(argv)

    # Internal: fix layout after split
    if args.fix_layout:
        if not args.agent_pane or not args.companion_pane:
            print(
                "Error: --agent-pane and --companion-pane are required with --fix-layout",
                file=sys.stderr,
            )
            sys.exit(1)
        _fix_layout(args.agent_pane, args.companion_pane)
        return

    # Internal: run as companion widget
    if args.companion:
        if not args.target_pane:
            print("Error: --target-pane is required with --companion", file=sys.stderr)
            sys.exit(1)
        _run_companion(args.target_pane)
        return

    # User-facing: launch agent + companion
    if not args.command:
        parser.print_help()
        sys.exit(1)

    command = " ".join(args.command)
    _launch(command)


def _launch(command: str) -> None:
    """Validate environment and launch the tmux split."""
    from tui_input.tmux import TmuxNotInstalledError, ensure_tmux_installed

    try:
        ensure_tmux_installed()
    except TmuxNotInstalledError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    from tui_input.launcher import launch

    launch(command)


def _run_companion(target_pane: str) -> None:
    """Run the companion app."""
    from tui_input.companion import run_companion

    run_companion(target_pane)


def _fix_layout(agent_pane: str, companion_pane: str) -> None:
    """Rejoin companion pane below agent if layout was broken by a split."""
    from tui_input.launcher import COMPANION_HEIGHT
    from tui_input.tmux import pane_exists, pane_width, rejoin_companion

    if not pane_exists(agent_pane) or not pane_exists(companion_pane):
        return

    agent_w = pane_width(agent_pane)
    companion_w = pane_width(companion_pane)
    if agent_w != companion_w:
        rejoin_companion(agent_pane, companion_pane, COMPANION_HEIGHT)


# Support running as `python -m tui_input`
if __name__ == "__main__":
    main()
