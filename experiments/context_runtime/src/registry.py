"""Minimal registry for callable entries (experiment)."""
from __future__ import annotations

from typing import Dict


class Registry:
    def __init__(self) -> None:
        self._entries: Dict[str, object] = {}

    def register(self, entry: object) -> None:
        name = getattr(entry, "name", None)
        if not isinstance(name, str) or not name:
            raise ValueError("Entry must have a non-empty name")
        if name in self._entries:
            raise ValueError(f"Duplicate entry name: {name}")
        self._entries[name] = entry

    def get(self, name: str) -> object:
        if name not in self._entries:
            raise KeyError(f"Unknown entry: {name}")
        return self._entries[name]
