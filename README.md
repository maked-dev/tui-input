# tui-input

[![CI](https://github.com/maked-dev/tui-input/actions/workflows/ci.yml/badge.svg)](https://github.com/maked-dev/tui-input/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/tui-input)](https://pypi.org/project/tui-input/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A terminal companion that pins a persistent input bar at the bottom of your tmux pane. Scroll freely through long TUI agent output while composing your response.

<!-- TODO: demo GIF -->
<!-- ![demo](https://github.com/maked-dev/tui-input/assets/demo.gif) -->

## The Problem

When using TUI-based AI agents (Claude Code, Codex CLI, etc.), long outputs force you to scroll up to read, then scroll back down to type. You end up:

- Losing your place in the output
- Writing responses in a separate editor, then copy-pasting
- Fighting the terminal scroll position

## The Solution

`tui-input` splits your terminal into two panes:

```
┌─────────────────────────────────────┐
│  Top pane (Claude Code / Codex etc) │
│  Scroll freely through long output  │
├─────────────────────────────────────┤  ← 3-10 lines, auto-resizing
│  Type your response here...         │
│  Enter to send · Shift+Enter: newline│
└─────────────────────────────────────┘
```

## Features

- **Pinned input bar** — always visible at the bottom, regardless of scroll position
- **Auto-resize** — companion grows from 3 to 10 lines as you type multi-line input
- **Bracketed paste** — safe multi-line text transfer via tmux buffers
- **Input history** — press `↑`/`↓` to recall previous inputs (persisted across sessions)
- **Agent-agnostic** — works with any terminal program, not just AI agents
- **Auto-cleanup** — companion exits when the agent exits

## Installation

### Requirements

- Python 3.10+
- tmux

### Install via pip/uv

```bash
# Using uv (recommended)
uv tool install tui-input

# Using pip
pip install tui-input
```

### One-liner (auto-detects agents + registers aliases)

```bash
curl -fsSL https://raw.githubusercontent.com/maked-dev/tui-input/main/install.sh | bash
```

This will:
1. Install `tui-input`
2. Detect installed agents (claude, codex, etc.)
3. Register shell aliases so you can just type `claude` instead of `tui-input claude`

To uninstall aliases:

```bash
curl -fsSL https://raw.githubusercontent.com/maked-dev/tui-input/main/install.sh | bash -s -- --uninstall
```

## Usage

```bash
# Basic usage
tui-input claude

# Any command works
tui-input "vim file.py"
tui-input htop

# With aliases installed (via install.sh), just type the agent name
claude
codex
```

### Key Bindings

| Key | Action |
|-----|--------|
| `Enter` | Send text to top pane + clear input |
| `Shift+Enter` | Insert newline (multi-line input) |
| `↑` (on empty) | Previous history entry |
| `↓` (on empty) | Next history entry |
| `Esc` | Clear all input |

### How It Works

1. `tui-input` creates a tmux vertical split (or a new session if not in tmux)
2. Your command runs in the top pane
3. A Textual-based companion widget runs in the bottom pane
4. Press `Enter` to send text to the top pane via `tmux paste-buffer`
5. When the top pane command exits, the companion auto-exits

## Development

```bash
# Clone and install
git clone https://github.com/maked-dev/tui-input.git
cd tui-input
uv sync

# Run tests
uv run pytest

# Lint and format
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Type check
uv run mypy src/
```

## License

[MIT](LICENSE)
