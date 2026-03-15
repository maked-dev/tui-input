"""Tests for JSON-based history management."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tui_input.history import MAX_ENTRIES, History, HistoryEntry

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def history_path(tmp_path: Path) -> Path:
    return tmp_path / "history.json"


@pytest.fixture
def history(history_path: Path) -> History:
    return History(path=history_path)


class TestHistoryEntry:
    def test_to_dict(self) -> None:
        entry = HistoryEntry(text="hello", timestamp="2026-01-01T00:00:00+00:00")
        assert entry.to_dict() == {
            "text": "hello",
            "timestamp": "2026-01-01T00:00:00+00:00",
        }

    def test_from_dict(self) -> None:
        data = {"text": "hello", "timestamp": "2026-01-01T00:00:00+00:00"}
        entry = HistoryEntry.from_dict(data)
        assert entry.text == "hello"
        assert entry.timestamp == "2026-01-01T00:00:00+00:00"


class TestHistoryAdd:
    def test_add_single_entry(self, history: History) -> None:
        history.add("hello")
        assert len(history.entries) == 1
        assert history.entries[0].text == "hello"

    def test_add_multiple_entries(self, history: History) -> None:
        history.add("first")
        history.add("second")
        history.add("third")
        assert len(history.entries) == 3
        assert [e.text for e in history.entries] == ["first", "second", "third"]

    def test_duplicate_moves_to_end(self, history: History) -> None:
        history.add("first")
        history.add("second")
        history.add("first")  # duplicate
        assert len(history.entries) == 2
        assert [e.text for e in history.entries] == ["second", "first"]

    def test_max_entries_trimmed(self, history: History) -> None:
        for i in range(MAX_ENTRIES + 20):
            history.add(f"entry-{i}")
        assert len(history.entries) == MAX_ENTRIES
        # The oldest entries should be trimmed
        assert history.entries[0].text == "entry-20"
        assert history.entries[-1].text == f"entry-{MAX_ENTRIES + 19}"


class TestHistoryPersistence:
    def test_save_and_load(self, history_path: Path) -> None:
        h1 = History(path=history_path)
        h1.add("persisted")
        h1.add("data")

        h2 = History(path=history_path)
        assert len(h2.entries) == 2
        assert h2.entries[0].text == "persisted"
        assert h2.entries[1].text == "data"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        deep_path = tmp_path / "a" / "b" / "c" / "history.json"
        h = History(path=deep_path)
        h.add("deep")
        assert deep_path.exists()

    def test_corrupted_file_falls_back_to_empty(self, history_path: Path) -> None:
        history_path.write_text("not valid json {{{", encoding="utf-8")
        h = History(path=history_path)
        assert h.entries == []

    def test_non_array_json_falls_back_to_empty(self, history_path: Path) -> None:
        history_path.write_text('{"key": "value"}', encoding="utf-8")
        h = History(path=history_path)
        assert h.entries == []

    def test_missing_file_starts_empty(self, history_path: Path) -> None:
        h = History(path=history_path)
        assert h.entries == []


class TestHistoryNavigation:
    def test_previous_on_empty_returns_none(self, history: History) -> None:
        assert history.get_previous() is None

    def test_previous_returns_most_recent_first(self, history: History) -> None:
        history.add("first")
        history.add("second")
        history.add("third")
        assert history.get_previous() == "third"
        assert history.get_previous() == "second"
        assert history.get_previous() == "first"

    def test_previous_stops_at_beginning(self, history: History) -> None:
        history.add("only")
        assert history.get_previous() == "only"
        assert history.get_previous() == "only"

    def test_next_without_previous_returns_none(self, history: History) -> None:
        history.add("entry")
        assert history.get_next() is None

    def test_previous_then_next(self, history: History) -> None:
        history.add("first")
        history.add("second")
        history.add("third")
        assert history.get_previous() == "third"
        assert history.get_previous() == "second"
        assert history.get_next() == "third"

    def test_next_past_end_returns_none(self, history: History) -> None:
        history.add("entry")
        assert history.get_previous() == "entry"
        assert history.get_next() is None

    def test_reset_navigation(self, history: History) -> None:
        history.add("first")
        history.add("second")
        history.get_previous()
        history.reset_navigation()
        assert history.get_previous() == "second"


class TestHistoryClear:
    def test_clear_removes_all_entries(self, history: History) -> None:
        history.add("one")
        history.add("two")
        history.clear()
        assert history.entries == []

    def test_clear_persists(self, history_path: Path) -> None:
        h = History(path=history_path)
        h.add("data")
        h.clear()

        h2 = History(path=history_path)
        assert h2.entries == []
