"""Minimal registry for callable entries.

The Registry is a simple name->entry dictionary that:
- Validates entries have non-empty names
- Prevents duplicate registrations
- Provides lookup by name
"""
from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .ctx import CallableEntry


class Registry:
    """Simple name-based registry for callable entries."""

    def __init__(self) -> None:
        self._entries: Dict[str, Any] = {}

    def register(self, entry: "CallableEntry") -> None:
        """Register an entry by its name.

        Args:
            entry: Entry with a `name` attribute

        Raises:
            ValueError: If entry has no name or name is duplicate
        """
        name = getattr(entry, "name", None)
        if not isinstance(name, str) or not name:
            raise ValueError("Entry must have a non-empty name")
        if name in self._entries:
            raise ValueError(f"Duplicate entry name: {name}")
        self._entries[name] = entry

    def get(self, name: str) -> "CallableEntry":
        """Look up an entry by name.

        Args:
            name: Entry name to look up

        Returns:
            The registered entry

        Raises:
            KeyError: If name is not registered
        """
        if name not in self._entries:
            raise KeyError(f"Unknown entry: {name}")
        return self._entries[name]

    def list_names(self) -> list[str]:
        """Return a list of all registered entry names."""
        return list(self._entries.keys())

    def __contains__(self, name: str) -> bool:
        """Check if a name is registered."""
        return name in self._entries

    def __len__(self) -> int:
        """Return the number of registered entries."""
        return len(self._entries)
