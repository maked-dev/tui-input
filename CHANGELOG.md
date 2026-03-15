# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-14

### Added

- Initial release
- Tmux-based split pane with companion input bar
- Multi-line input with auto-resizing (3-10 lines)
- Bracketed paste for safe text transfer
- JSON-based input history with up/down navigation
- Agent-agnostic design (works with any terminal command)
- Auto-cleanup when the target pane exits
- One-liner install script with agent detection and alias registration
- Key bindings: Enter (send), Shift+Enter (newline), Esc (clear), arrows (history)

[Unreleased]: https://github.com/maked-dev/tui-input/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/maked-dev/tui-input/releases/tag/v0.1.0
