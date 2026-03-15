"""JSON-based input history management."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HISTORY_PATH = Path.home() / ".local" / "share" / "tui-input" / "history.json"
MAX_ENTRIES = 100


@dataclass
class HistoryEntry:
    """A single history entry."""

    text: str
    timestamp: str

    def to_dict(self) -> dict[str, str]:
        """Serialize to a JSON-compatible dict."""
        return {"text": self.text, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryEntry:
        """Deserialize from a dict."""
        return cls(text=str(data["text"]), timestamp=str(data["timestamp"]))


@dataclass
class History:
    """Manages a JSON-based input history file.

    Entries are stored as a JSON array of objects with 'text' and 'timestamp' fields.
    Duplicate entries are moved to the end (most recent position).
    Maximum entries are capped at ``MAX_ENTRIES``.
    """

    path: Path = field(default_factory=lambda: DEFAULT_HISTORY_PATH)
    entries: list[HistoryEntry] = field(default_factory=list)
    _index: int = field(default=-1, repr=False)

    def __post_init__(self) -> None:
        self.load()

    def load(self) -> None:
        """Load history from the JSON file.

        Falls back to an empty list on missing file or corruption.
        """
        if not self.path.exists():
            self.entries = []
            return
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, list):
                self.entries = []
                return
            self.entries = [HistoryEntry.from_dict(item) for item in data]
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            self.entries = []

    def save(self) -> None:
        """Persist current entries to the JSON file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [entry.to_dict() for entry in self.entries]
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, text: str) -> None:
        """Add a new entry. Duplicates are moved to the end.

        Empty or whitespace-only text is silently ignored.
        """
        if not text or not text.strip():
            return
        # Remove existing duplicate.
        self.entries = [e for e in self.entries if e.text != text]
        self.entries.append(
            HistoryEntry(
                text=text,
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
            )
        )
        # Trim to max entries.
        if len(self.entries) > MAX_ENTRIES:
            self.entries = self.entries[-MAX_ENTRIES:]
        self.save()
        self._index = -1

    def get_previous(self) -> str | None:
        """Navigate backward in history. Returns None if at the beginning."""
        if not self.entries:
            return None
        if self._index == -1:
            self._index = len(self.entries) - 1
        elif self._index > 0:
            self._index -= 1
        else:
            return self.entries[0].text
        return self.entries[self._index].text

    def get_next(self) -> str | None:
        """Navigate forward in history. Returns None if past the end."""
        if not self.entries or self._index == -1:
            return None
        if self._index < len(self.entries) - 1:
            self._index += 1
            return self.entries[self._index].text
        # Past the end — reset index.
        self._index = -1
        return None

    def reset_navigation(self) -> None:
        """Reset the navigation index."""
        self._index = -1

    def clear(self) -> None:
        """Clear all history entries."""
        self.entries = []
        self._index = -1
        self.save()
