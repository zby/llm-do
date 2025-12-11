"""Display backend abstractions for the async CLI."""
from __future__ import annotations

import asyncio
import json
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, Mapping, TextIO


@dataclass
class CLIEvent:
    """Structured event emitted by the async runtime."""

    kind: Literal["runtime_event", "deferred_tool", "approval_request"]
    payload: Any


class DisplayBackend(ABC):
    """Interface for rendering CLI events (JSON, Textual, etc.)."""

    wants_runtime_events: bool = True

    async def start(self) -> None:  # pragma: no cover - simple default
        return None

    async def stop(self) -> None:  # pragma: no cover - simple default
        return None

    def handle_event(self, event: CLIEvent) -> None:
        if event.kind == "runtime_event":
            self.display_runtime_event(event.payload)
        elif event.kind == "deferred_tool":
            self.display_deferred_tool(event.payload)
        else:  # pragma: no cover - defensive branch
            self.display_runtime_event(event.payload)

    @abstractmethod
    def display_runtime_event(self, payload: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def display_deferred_tool(self, payload: Mapping[str, Any]) -> None:
        raise NotImplementedError


class JsonDisplayBackend(DisplayBackend):
    """JSONL renderer for headless/automation scenarios."""

    def __init__(self, stream: TextIO | None = None):
        self.stream = stream or sys.stderr

    def _write_record(self, record: Mapping[str, Any]) -> None:
        json.dump(record, self.stream, default=self._default)
        self.stream.write("\n")
        self.stream.flush()

    @staticmethod
    def _default(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return repr(value)

    def display_runtime_event(self, payload: Any) -> None:
        self._write_record({"kind": "runtime_event", "payload": payload})

    def display_deferred_tool(self, payload: Mapping[str, Any]) -> None:
        self._write_record({"kind": "deferred_tool", "payload": payload})


class TextualDisplayBackend(DisplayBackend):
    """Textual TUI backend that forwards events to a Textual app.

    This backend works by forwarding events to a queue that the Textual
    app consumes. The app runs in its own async context alongside the
    worker.
    """

    def __init__(self, event_queue: asyncio.Queue[Any]):
        self._queue = event_queue

    def display_runtime_event(self, payload: Any) -> None:
        self._queue.put_nowait(CLIEvent(kind="runtime_event", payload=payload))

    def display_deferred_tool(self, payload: Mapping[str, Any]) -> None:
        self._queue.put_nowait(CLIEvent(kind="deferred_tool", payload=payload))
