"""Exit confirmation state (UI-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExitDecision(str, Enum):
    IGNORE = "ignore"
    PROMPT = "prompt"
    EXIT = "exit"


@dataclass(slots=True)
class ExitConfirmationController:
    """Two-step quit confirmation for idle mode."""

    _requested: bool = False

    def reset(self) -> None:
        self._requested = False

    def request(self) -> ExitDecision:
        if not self._requested:
            self._requested = True
            return ExitDecision.PROMPT
        return ExitDecision.EXIT

