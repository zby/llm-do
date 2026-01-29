"""Agent lifecycle and chat message history (UI-agnostic)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Coroutine

RunTurnFn = Callable[[str], Awaitable[list[Any] | None]]


@dataclass(slots=True)
class AgentRunner:
    """Manages a single in-flight agent task and conversation message history."""

    run_turn: RunTurnFn | None = None
    message_history: list[Any] = field(default_factory=list)
    _task: asyncio.Task[Any] | None = None

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start_background(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        if self.is_running():
            raise RuntimeError("Agent task already running")
        self._task = asyncio.create_task(coro)
        return self._task

    def set_message_history(self, history: list[Any] | None) -> None:
        self.message_history = list(history or [])

    async def run_turn_and_update(self, prompt: str) -> list[Any] | None:
        if self.run_turn is None:
            raise RuntimeError("Conversation runner not configured")
        new_history = await self.run_turn(prompt)
        if new_history is not None:
            self.message_history = list(new_history)
        return new_history

    def start_turn_task(self, prompt: str) -> asyncio.Task[list[Any] | None]:
        if self.is_running():
            raise RuntimeError("Agent task already running")
        task = asyncio.create_task(self.run_turn_and_update(prompt))
        self._task = task
        return task

