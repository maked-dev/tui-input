# Contributing to tui-input

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/maked-dev/tui-input.git
   cd tui-input
   ```

2. **Install dependencies** (using [uv](https://github.com/astral-sh/uv)):
   ```bash
   uv sync
   ```

3. **Verify your setup:**
   ```bash
   uv run pytest
   uv run ruff check src/ tests/
   uv run mypy src/
   ```

## Code Style

- **Formatter/Linter:** [Ruff](https://github.com/astral-sh/ruff) — configured in `pyproject.toml`
- **Type checking:** [mypy](https://mypy-lang.org/) in strict mode
- **Line length:** 100 characters
- **Python version:** 3.10+ (use `from __future__ import annotations` in all modules)

Run before committing:

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
uv run mypy src/
```

## Testing

- Tests live in `tests/`
- Use [pytest](https://pytest.org/) with [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) for async tests
- Textual apps are tested using [Textual's pilot API](https://textual.textualize.io/guide/testing/)
- All tmux calls should be mocked — tests must not require tmux to be installed

```bash
uv run pytest              # Run all tests
uv run pytest -x           # Stop on first failure
uv run pytest -v           # Verbose output
uv run pytest tests/test_history.py  # Run a specific test file
```

## Pull Request Process

1. Fork the repo and create a feature branch from `main`
2. Write tests for any new functionality
3. Ensure all checks pass: `ruff check`, `ruff format --check`, `mypy`, `pytest`
4. Write a clear PR description explaining **what** and **why**
5. Keep PRs focused — one feature or fix per PR

## Commit Messages

- Use present tense ("Add feature" not "Added feature")
- Keep the first line under 72 characters
- Reference issues when applicable (e.g., "Fix #42")

## Reporting Bugs

Use the [bug report template](https://github.com/maked-dev/tui-input/issues/new?template=bug_report.yml) and include:

- OS and terminal emulator
- tmux version (`tmux -V`)
- Python version (`python3 --version`)
- Steps to reproduce

## Feature Requests

Use the [feature request template](https://github.com/maked-dev/tui-input/issues/new?template=feature_request.yml).
