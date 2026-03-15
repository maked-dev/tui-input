# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Build & Test Commands

```bash
uv run pytest tests/ -v          # Run all tests
uv run pytest tests/ -v --cov    # Run with coverage
uv run ruff check src/ tests/    # Lint
uv run ruff format src/ tests/   # Format
uv run mypy src/                 # Type check
```

## Architecture

```
cli.py          CLI entry point (argparse, dispatches to internal modes)
  ↓
launcher.py     Tmux environment setup (split pane, launch companion + agent)
  ↓
companion.py    Textual app — input bar widget with key forwarding
  ↓
tmux.py         Low-level tmux operations (pane queries, text pasting, hooks)
history.py      JSON-based persistent input history
```

### Key Design Decisions

- **Companion pane ID via `TMUX_PANE` env var**: `tmux display-message -p` returns the *selected* pane, not the pane the process runs in. Always use `os.environ.get("TMUX_PANE")` for the companion's own pane ID.
- **Shell vs Direct mode**: Inside tmux, the pane runs a shell that spawns the agent. Outside tmux, the pane runs the agent directly. `_check_target_alive` uses `_is_shell()` to pick the right exit detection strategy.
- **IME deferred actions**: Enter/Shift+Enter handlers use a 50ms timer to let terminal IME settle before acting. Terminal IME composition characters are NOT sent to the app — they exist only in the terminal's overlay.
- **Separate paste + Enter**: `submit_to_pane` uses `paste-buffer` for text and `send-keys Enter` separately, so the target app reliably treats Enter as submit.
- **Hook commands wrapped in `run-shell`**: tmux hooks expect tmux commands, not shell commands. Shell commands must be wrapped in `run-shell '...'`.
- **Dynamic pane addressing**: Never use hardcoded pane indices (`.0`). Use `list-panes -F '#{pane_id}'` to handle any `pane-base-index` setting.

## Conventions

- Language: code identifiers in English, comments/docs in English
- All modules use `from __future__ import annotations`
- Type hints on all function signatures; `mypy --strict` must pass
- `contextlib.suppress(subprocess.CalledProcessError)` over bare `except Exception`
- Constants at module level, no magic numbers in logic
