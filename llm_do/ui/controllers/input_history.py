"""Input history navigation logic (UI-agnostic).

Encapsulates the up/down history behavior used by the Textual input box.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class HistoryNavigation:
    """Result of a history navigation attempt."""

    handled: bool
    text: str | None = None


@dataclass(slots=True)
class InputHistoryController:
    """State machine for navigating user input history."""

    entries: list[str] = field(default_factory=list)
    _index: int | None = None
    _draft: str = ""

    def record_submission(self, text: str) -> None:
        """Record a submitted input and reset navigation state."""
        self.entries.append(text)
        self._index = None
        self._draft = ""

    def previous(self, current_text: str) -> HistoryNavigation:
        """Navigate to the previous history entry (older)."""
        if not self.entries:
            return HistoryNavigation(handled=False)

        if self._index is None:
            self._draft = current_text
            self._index = len(self.entries) - 1
            return HistoryNavigation(handled=True, text=self.entries[self._index])

        if self._index > 0:
            self._index -= 1
            return HistoryNavigation(handled=True, text=self.entries[self._index])

        # Already at oldest entry; consume the key but don't change text.
        return HistoryNavigation(handled=True, text=None)

    def next(self) -> HistoryNavigation:
        """Navigate to the next history entry (newer) or back to the draft."""
        if self._index is None:
            return HistoryNavigation(handled=False)

        if self._index < len(self.entries) - 1:
            self._index += 1
            return HistoryNavigation(handled=True, text=self.entries[self._index])

        # Move past the newest entry back to the in-progress draft.
        draft = self._draft
        self._index = None
        self._draft = ""
        return HistoryNavigation(handled=True, text=draft)

