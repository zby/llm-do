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


class HeadlessDisplayBackend(DisplayBackend):
    """Plain text renderer for headless/non-interactive scenarios.

    Renders events as human-readable text to stderr, showing the same
    information as the TUI mode.
    """

    def __init__(self, stream: TextIO | None = None):
        self.stream = stream or sys.stderr
        self._current_worker: str = ""

    def _write(self, text: str) -> None:
        self.stream.write(text)
        self.stream.write("\n")
        self.stream.flush()

    def display_runtime_event(self, payload: Any) -> None:
        # Handle dict payloads (serialized events from message callback)
        if isinstance(payload, dict):
            self._handle_dict_event(payload)
            return

        # Handle string payloads (errors, status)
        if isinstance(payload, str):
            self._write(f"  {payload}")
            return

        # Handle pydantic-ai event types directly
        event_type = type(payload).__name__
        if event_type == "PartDeltaEvent":
            # Streaming text - skip for now (we show complete parts)
            pass
        elif event_type == "PartStartEvent":
            pass
        elif event_type == "FinalResultEvent":
            self._write("  ✓ Response complete")

    def _handle_dict_event(self, payload: dict) -> None:
        """Handle dict-based event payloads from message callback."""
        from pydantic_ai.messages import (
            PartEndEvent,
            TextPart,
            FunctionToolCallEvent,
            FunctionToolResultEvent,
        )

        worker = payload.get("worker", "worker")

        # Handle initial_request preview
        if "initial_request" in payload:
            self._write(f"[{worker}] Starting...")
            return

        # Handle status updates
        if "status" in payload:
            status = payload.get("status")
            if isinstance(status, dict):
                phase = status.get("phase", "")
                state = status.get("state", "")
                model = status.get("model", "")
                if phase and state:
                    if model:
                        self._write(f"[{worker}] {phase} {state} ({model})")
                    else:
                        self._write(f"[{worker}] {phase} {state}")
                else:
                    self._write(f"[{worker}] {status}")
            else:
                self._write(f"[{worker}] {status}")
            return

        # Get the actual event object
        event = payload.get("event")
        if event is None:
            return

        # Handle pydantic-ai event types
        if isinstance(event, PartEndEvent):
            part = event.part
            if isinstance(part, TextPart):
                # Display model response text
                self._write(f"\n[{worker}] Response:")
                for line in part.content.split("\n"):
                    self._write(f"  {line}")
        elif isinstance(event, FunctionToolCallEvent):
            tool_name = getattr(event.part, "tool_name", "tool")
            args = getattr(event.part, "args", {})
            self._write(f"\n[{worker}] Tool call: {tool_name}")
            if args:
                # Show truncated args
                args_str = str(args)
                if len(args_str) > 200:
                    args_str = args_str[:200] + "..."
                self._write(f"  Args: {args_str}")
        elif isinstance(event, FunctionToolResultEvent):
            result = event.result
            tool_name = getattr(result, "tool_name", "tool")
            self._write(f"\n[{worker}] Tool result: {tool_name}")
            # Show truncated result
            result_str = str(result.content) if hasattr(result, "content") else str(result)
            if len(result_str) > 500:
                result_str = result_str[:500] + "..."
            for line in result_str.split("\n")[:10]:  # Limit lines
                self._write(f"  {line}")
            if result_str.count("\n") > 10:
                self._write(f"  ... ({result_str.count(chr(10)) - 10} more lines)")

    def display_deferred_tool(self, payload: Mapping[str, Any]) -> None:
        tool_name = payload.get("tool_name", "tool")
        status = payload.get("status", "pending")
        self._write(f"  Deferred tool '{tool_name}': {status}")


class RichDisplayBackend(DisplayBackend):
    """Rich-formatted renderer for capturing styled output.

    Uses Rich Console for colorful, formatted output. When writing to a
    StringIO buffer, use force_terminal=True to ensure ANSI codes are
    included for later display in a terminal.
    """

    def __init__(self, stream: TextIO | None = None, force_terminal: bool = False):
        from rich.console import Console

        self.stream = stream or sys.stderr
        self.console = Console(
            file=self.stream,
            force_terminal=force_terminal,
            width=120,  # Reasonable width for captured output
        )

    def display_runtime_event(self, payload: Any) -> None:
        # Debug: show payload type
        self.console.print(f"[dim]DEBUG: payload type={type(payload).__name__}[/dim]")

        # Handle dict payloads (serialized events from message callback)
        if isinstance(payload, dict):
            self._handle_dict_event(payload)
            return

        # Handle string payloads (errors, status)
        if isinstance(payload, str):
            self.console.print(f"  {payload}")
            return

        # Handle pydantic-ai event types directly
        event_type = type(payload).__name__
        if event_type == "PartDeltaEvent":
            # Streaming text - skip for now (we show complete parts)
            pass
        elif event_type == "PartStartEvent":
            pass
        elif event_type == "FinalResultEvent":
            self.console.print("  [green]✓[/green] Response complete")

    def _handle_dict_event(self, payload: dict) -> None:
        """Handle dict-based event payloads from message callback."""
        from pydantic_ai.messages import (
            PartEndEvent,
            TextPart,
            FunctionToolCallEvent,
            FunctionToolResultEvent,
        )

        worker = payload.get("worker", "worker")

        # Handle initial_request preview
        if "initial_request" in payload:
            self.console.print(f"[bold cyan][{worker}][/bold cyan] Starting...")
            return

        # Handle status updates
        if "status" in payload:
            status = payload.get("status")
            if isinstance(status, dict):
                phase = status.get("phase", "")
                state = status.get("state", "")
                model = status.get("model", "")
                if phase and state:
                    if model:
                        self.console.print(
                            f"[dim][{worker}][/dim] {phase} {state} [dim]({model})[/dim]"
                        )
                    else:
                        self.console.print(f"[dim][{worker}][/dim] {phase} {state}")
                else:
                    self.console.print(f"[dim][{worker}][/dim] {status}")
            else:
                self.console.print(f"[dim][{worker}][/dim] {status}")
            return

        # Get the actual event object
        event = payload.get("event")
        if event is None:
            return

        # Handle pydantic-ai event types
        if isinstance(event, PartEndEvent):
            part = event.part
            if isinstance(part, TextPart):
                # Display model response text
                self.console.print(f"\n[bold green][{worker}][/bold green] Response:")
                for line in part.content.split("\n"):
                    self.console.print(f"  {line}")
        elif isinstance(event, FunctionToolCallEvent):
            tool_name = getattr(event.part, "tool_name", "tool")
            args = getattr(event.part, "args", {})
            self.console.print(
                f"\n[bold yellow][{worker}][/bold yellow] Tool call: [yellow]{tool_name}[/yellow]"
            )
            if args:
                # Show truncated args
                args_str = str(args)
                if len(args_str) > 200:
                    args_str = args_str[:200] + "..."
                self.console.print(f"  [dim]Args:[/dim] {args_str}")
        elif isinstance(event, FunctionToolResultEvent):
            result = event.result
            tool_name = getattr(result, "tool_name", "tool")
            self.console.print(
                f"\n[bold blue][{worker}][/bold blue] Tool result: [blue]{tool_name}[/blue]"
            )
            # Show truncated result
            result_str = str(result.content) if hasattr(result, "content") else str(result)
            if len(result_str) > 500:
                result_str = result_str[:500] + "..."
            for line in result_str.split("\n")[:10]:  # Limit lines
                self.console.print(f"  {line}")
            if result_str.count("\n") > 10:
                self.console.print(f"  [dim]... ({result_str.count(chr(10)) - 10} more lines)[/dim]")

    def display_deferred_tool(self, payload: Mapping[str, Any]) -> None:
        tool_name = payload.get("tool_name", "tool")
        status = payload.get("status", "pending")
        self.console.print(f"  Deferred tool '[yellow]{tool_name}[/yellow]': {status}")


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
