"""Shared test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tmp_history_path(tmp_path: Path) -> Path:
    """Return a temporary path for history file."""
    return tmp_path / "tui-input" / "history.json"
