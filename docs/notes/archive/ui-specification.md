# UI System Specification

This document provides a detailed specification of the llm-do UI system, sufficient for reimplementation.

## Overview

The UI system displays worker execution events in real-time. It supports four output modes:
1. **TUI** - Interactive Textual terminal application (default)
2. **Rich** - Colorful formatted text (non-interactive)
3. **Headless** - Plain text (non-interactive)
4. **JSON** - Machine-readable JSONL (non-interactive)

**Scope:** This specification covers single-worker execution. Multiple concurrent workers would require additional UI considerations (worker grouping, parallel progress indicators) and is deferred to a future version. The `worker` field on events is included for forward compatibility.

### Output Stream Design

All modes follow the same output stream convention:
- **Events** -> `stderr` (progress, tool calls, status updates)
- **Final result** -> `stdout` (the last assistant message / worker output)

This enables piping: `llm-do "summarize this" < input.txt > summary.txt` works because progress goes to stderr while only the result goes to stdout.

Plain text output is strict ASCII (no ANSI, no Unicode). Use tokens like `[OK]`, `[WARN]`, and `[ERROR]`.

**TUI mode** captures both streams in buffers during execution, then prints them after the TUI exits:
- Events buffer -> printed to stderr
- Result buffer -> printed to stdout

This ensures consistent behavior whether running interactively or in a pipeline.

## Design Principles

### Events Know How to Render Themselves

The core design principle is that **each `UIEvent` subclass is responsible for knowing how to render itself in different formats**. This follows the principle of "Tell, Don't Ask" - instead of backends inspecting event payloads and deciding how to render them, events are told to render themselves.

**Benefits:**
- **No code duplication** - Rendering logic is in one place per event type
- **Easy to extend** - Adding a new event type only requires implementing the render methods
- **Type safety** - Typed events instead of `Any` payloads
- **Testable** - Each event's rendering can be unit tested independently

### Current Implementation Notes

The codebase already follows this design:

- Raw callback payloads are parsed in `llm_do/ui/parser.py` into `UIEvent` instances.
- Rendering is centralized in `UIEvent.render_*` and `UIEvent.create_widget`.
- `LlmDoApp` only manages approval state and final-result capture.
- `MessageContainer` handles streaming and widget mounting.

## Architecture

```
Worker Execution
  |
  v
Event Parser
  |
  v
Event Queue
  |
  v
DisplayBackend
  |-- TextualDisplayBackend (event.create_widget)
  |-- RichDisplayBackend (event.render_rich)
  |-- JsonDisplayBackend (event.render_json)
  `-- HeadlessDisplayBackend (event.render_text)
```

## Event Type Hierarchy

### UIEvent Base Class

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import RenderableType
    from textual.widget import Widget


@dataclass
class UIEvent(ABC):
    """Base class for all UI events.

    Each event knows how to render itself in multiple formats.
    The render methods receive context (verbosity) as parameters.
    """
    worker: str = ""

    @abstractmethod
    def render_rich(self, verbosity: int = 0) -> "RenderableType | None":
        """Render as Rich Console output.

        Args:
            verbosity: 0=minimal, 1=normal, 2=verbose

        Returns:
            A Rich renderable (Text, Panel, Group, etc.) or None to skip display.
        """
        ...

    @abstractmethod
    def render_text(self, verbosity: int = 0) -> str | None:
        """Render as plain text (ASCII only, no ANSI codes).

        Args:
            verbosity: 0=minimal, 1=normal, 2=verbose

        Returns:
            Plain ASCII string or None to skip display.
        """
        ...

    @abstractmethod
    def render_json(self) -> dict[str, Any]:
        """Render as JSON-serializable dict.

        Returns:
            Dictionary suitable for json.dumps().
        """
        ...

    @abstractmethod
    def create_widget(self) -> "Widget | None":
        """Create a Textual widget for TUI display.

        Returns:
            A Textual Widget instance or None to skip display.
        """
        ...
```

### Event Subclasses

#### InitialRequestEvent

Displayed when a worker starts processing a request.

```python
@dataclass
class InitialRequestEvent(UIEvent):
    """Event emitted when worker receives initial request."""
    instructions: str = ""
    user_input: str = ""
    attachments: list[str] = field(default_factory=list)

    # Rendering constants
    MAX_INPUT_DISPLAY: ClassVar[int] = 200

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.text import Text
        from rich.console import Group

        parts = [Text(f"[{self.worker}] ", style="bold cyan") + Text("Starting...")]
        if self.user_input:
            display_input = self._truncate(self.user_input, self.MAX_INPUT_DISPLAY)
            parts.append(Text("  Prompt: ", style="dim") + Text(display_input))
        return Group(*parts)

    def render_text(self, verbosity: int = 0) -> str:
        lines = [f"[{self.worker}] Starting..."]
        if self.user_input:
            display_input = self._truncate(self.user_input, self.MAX_INPUT_DISPLAY)
            lines.append(f"  Prompt: {display_input}")
        return "\n".join(lines)

    def render_json(self) -> dict[str, Any]:
        return {
            "type": "initial_request",
            "worker": self.worker,
            "instructions": self.instructions,
            "user_input": self.user_input,
            "attachments": self.attachments,
        }

    def create_widget(self) -> "Widget":
        from llm_do.ui.widgets.messages import StatusMessage
        return StatusMessage(f"Starting: {self._truncate(self.user_input, 100)}")

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        return text[:max_len] + "..." if len(text) > max_len else text
```

#### StatusEvent

Displays phase transitions and model info.

```python
@dataclass
class StatusEvent(UIEvent):
    """Event emitted for phase/state transitions."""
    phase: str = ""         # e.g., "model_request", "tool_execution"
    state: str = ""         # e.g., "start", "end", "error"
    model: str = ""         # e.g., "anthropic:claude-haiku-4-5"
    duration_sec: float | None = None

    def render_rich(self, verbosity: int = 0) -> "RenderableType | None":
        from rich.text import Text

        if not self.phase:
            return None

        text = Text(f"[{self.worker}] ", style="dim")
        text.append(f"{self.phase} {self.state}")
        if self.model:
            text.append(f" ({self.model})", style="dim")
        if self.duration_sec is not None:
            text.append(f" [{self.duration_sec:.2f}s]", style="dim")
        return text

    def render_text(self, verbosity: int = 0) -> str | None:
        if not self.phase:
            return None
        result = f"[{self.worker}] {self.phase} {self.state}"
        if self.model:
            result += f" ({self.model})"
        if self.duration_sec is not None:
            result += f" [{self.duration_sec:.2f}s]"
        return result

    def render_json(self) -> dict[str, Any]:
        return {
            "type": "status",
            "worker": self.worker,
            "phase": self.phase,
            "state": self.state,
            "model": self.model,
            "duration_sec": self.duration_sec,
        }

    def create_widget(self) -> "Widget":
        from llm_do.ui.widgets.messages import StatusMessage
        text = f"{self.phase} {self.state}"
        if self.model:
            text += f" ({self.model})"
        return StatusMessage(text)
```

#### TextResponseEvent

Displays model text responses (complete or streaming).

```python
@dataclass
class TextResponseEvent(UIEvent):
    """Event emitted for model text responses."""
    content: str = ""
    is_complete: bool = True   # False for streaming start
    is_delta: bool = False     # True for partial streaming updates

    def render_rich(self, verbosity: int = 0) -> "RenderableType | None":
        from rich.text import Text
        from rich.console import Group

        # Streaming deltas only shown at verbosity >= 2
        if self.is_delta:
            if verbosity >= 2:
                return Text(self.content, end="")
            return None

        # Complete responses
        if self.is_complete:
            header = Text(f"\n[{self.worker}] ", style="bold green") + Text("Response:")
            content = Text("\n".join(f"  {line}" for line in self.content.split("\n")))
            return Group(header, content)

        # Start of streaming (verbosity >= 1)
        if verbosity >= 1:
            return Text(f"[{self.worker}] ", style="dim") + Text("Generating response...", style="dim")
        return None

    def render_text(self, verbosity: int = 0) -> str | None:
        if self.is_delta:
            return self.content if verbosity >= 2 else None
        if self.is_complete:
            lines = [f"\n[{self.worker}] Response:"]
            lines.extend(f"  {line}" for line in self.content.split("\n"))
            return "\n".join(lines)
        if verbosity >= 1:
            return f"[{self.worker}] Generating response..."
        return None

    def render_json(self) -> dict[str, Any]:
        return {
            "type": "text_response",
            "worker": self.worker,
            "content": self.content,
            "is_complete": self.is_complete,
            "is_delta": self.is_delta,
        }

    def create_widget(self) -> "Widget | None":
        return None  # TUI handles streaming and finalization via MessageContainer
```

#### ToolCallEvent

Displays tool invocations.

```python
@dataclass
class ToolCallEvent(UIEvent):
    """Event emitted when a tool is called."""
    tool_name: str = ""
    tool_call_id: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    args_json: str = ""  # Raw JSON string for display

    MAX_ARGS_DISPLAY: ClassVar[int] = 200

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.text import Text
        from rich.console import Group

        header = (
            Text(f"\n[{self.worker}] ", style="bold yellow") +
            Text("Tool call: ") +
            Text(self.tool_name, style="yellow")
        )
        parts = [header]
        if self.args or self.args_json:
            args_str = self.args_json or str(self.args)
            args_display = self._truncate(args_str, self.MAX_ARGS_DISPLAY)
            parts.append(Text("  Args: ", style="dim") + Text(args_display))
        return Group(*parts)

    def render_text(self, verbosity: int = 0) -> str:
        lines = [f"\n[{self.worker}] Tool call: {self.tool_name}"]
        if self.args or self.args_json:
            args_str = self.args_json or str(self.args)
            args_display = self._truncate(args_str, self.MAX_ARGS_DISPLAY)
            lines.append(f"  Args: {args_display}")
        return "\n".join(lines)

    def render_json(self) -> dict[str, Any]:
        return {
            "type": "tool_call",
            "worker": self.worker,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "args": self.args,
        }

    def create_widget(self) -> "Widget":
        from llm_do.ui.widgets.messages import ToolCallMessage
        return ToolCallMessage(self.tool_name, self.args)

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        return text[:max_len] + "..." if len(text) > max_len else text
```

#### ToolResultEvent

Displays tool execution results.

```python
@dataclass
class ToolResultEvent(UIEvent):
    """Event emitted when a tool returns a result."""
    tool_name: str = ""
    tool_call_id: str = ""
    content: str = ""
    is_error: bool = False

    MAX_RESULT_DISPLAY: ClassVar[int] = 500
    MAX_RESULT_LINES: ClassVar[int] = 10

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.text import Text
        from rich.console import Group

        style = "red" if self.is_error else "blue"
        label = "Tool error" if self.is_error else "Tool result"
        header = (
            Text(f"\n[{self.worker}] ", style=f"bold {style}") +
            Text(f"{label}: ") +
            Text(self.tool_name, style=style)
        )

        content_display = self._truncate_content(self.content)
        content_lines = [Text(f"  {line}") for line in content_display.split("\n")]

        return Group(header, *content_lines)

    def render_text(self, verbosity: int = 0) -> str:
        label = "Tool error" if self.is_error else "Tool result"
        lines = [f"\n[{self.worker}] {label}: {self.tool_name}"]
        content_display = self._truncate_content(self.content)
        lines.extend(f"  {line}" for line in content_display.split("\n"))
        return "\n".join(lines)

    def render_json(self) -> dict[str, Any]:
        return {
            "type": "tool_result",
            "worker": self.worker,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "content": self.content,
            "is_error": self.is_error,
        }

    def create_widget(self) -> "Widget":
        from llm_do.ui.widgets.messages import ToolResultMessage
        return ToolResultMessage(self.tool_name, self.content)

    def _truncate_content(self, text: str) -> str:
        """Truncate content by both length and line count."""
        if len(text) > self.MAX_RESULT_DISPLAY:
            text = text[:self.MAX_RESULT_DISPLAY] + "..."
        lines = text.split("\n")
        if len(lines) > self.MAX_RESULT_LINES:
            remaining = len(lines) - self.MAX_RESULT_LINES
            text = "\n".join(lines[:self.MAX_RESULT_LINES]) + f"\n... ({remaining} more lines)"
        return text
```

#### DeferredToolEvent

Displays async/deferred tool execution status.

```python
@dataclass
class DeferredToolEvent(UIEvent):
    """Event emitted for deferred (async) tool status updates."""
    tool_name: str = ""
    status: str = ""  # "pending", "running", "complete", "error"

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.text import Text

        status_style = {
            "pending": "dim",
            "running": "yellow",
            "complete": "green",
            "error": "red",
        }.get(self.status, "")

        return (
            Text("  Deferred tool '") +
            Text(self.tool_name, style="yellow") +
            Text("': ") +
            Text(self.status, style=status_style)
        )

    def render_text(self, verbosity: int = 0) -> str:
        return f"  Deferred tool '{self.tool_name}': {self.status}"

    def render_json(self) -> dict[str, Any]:
        return {
            "type": "deferred_tool",
            "worker": self.worker,
            "tool_name": self.tool_name,
            "status": self.status,
        }

    def create_widget(self) -> "Widget":
        from llm_do.ui.widgets.messages import StatusMessage
        return StatusMessage(f"Deferred tool '{self.tool_name}': {self.status}")
```

#### CompletionEvent

Displayed when worker completes.

```python
@dataclass
class CompletionEvent(UIEvent):
    """Event emitted when worker completes successfully."""

    def render_rich(self, verbosity: int = 0) -> "RenderableType | None":
        from rich.text import Text

        if verbosity >= 1:
            return Text(f"[{self.worker}] ", style="dim") + Text("[OK] Complete", style="green")
        return None

    def render_text(self, verbosity: int = 0) -> str | None:
        if verbosity >= 1:
            return f"[{self.worker}] [OK] Complete"
        return None

    def render_json(self) -> dict[str, Any]:
        return {
            "type": "completion",
            "worker": self.worker,
        }

    def create_widget(self) -> "Widget | None":
        return None  # Completion is handled at app level
```

#### ErrorEvent

Displayed when an error occurs during execution.

```python
@dataclass
class ErrorEvent(UIEvent):
    """Event emitted when an error occurs."""
    message: str = ""
    error_type: str = ""  # e.g., "tool_error", "model_error", "timeout"
    traceback: str | None = None  # Optional, shown at verbosity >= 2

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.text import Text
        from rich.panel import Panel

        content = Text(self.message, style="red")
        if verbosity >= 2 and self.traceback:
            content.append(f"\n\n{self.traceback}", style="dim red")
        return Panel(content, title=f"ERROR: {self.error_type}", border_style="red")

    def render_text(self, verbosity: int = 0) -> str:
        lines = [f"[{self.worker}] ERROR ({self.error_type}): {self.message}"]
        if verbosity >= 2 and self.traceback:
            lines.append(self.traceback)
        return "\n".join(lines)

    def render_json(self) -> dict[str, Any]:
        return {
            "type": "error",
            "worker": self.worker,
            "error_type": self.error_type,
            "message": self.message,
            "traceback": self.traceback,
        }

    def create_widget(self) -> "Widget":
        from llm_do.ui.widgets.messages import ErrorMessage
        return ErrorMessage(self.message, self.error_type)
```

#### ApprovalRequestEvent

Displays interactive tool approval requests (TUI only).

Fields map from `ApprovalRequest`:
- `tool_name` <- `ApprovalRequest.tool_name`
- `reason` <- `ApprovalRequest.description`
- `args` <- `ApprovalRequest.tool_args`
- `request` <- The full `ApprovalRequest` object (for widgets that need it)

```python
from pydantic_ai_blocking_approval import ApprovalRequest

@dataclass
class ApprovalRequestEvent(UIEvent):
    """Event emitted when tool requires user approval."""
    tool_name: str = ""
    reason: str = ""  # Maps to ApprovalRequest.description
    args: dict[str, Any] = field(default_factory=dict)
    request: ApprovalRequest | None = None  # The actual ApprovalRequest object

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.panel import Panel
        from rich.text import Text

        content = Text()
        content.append(f"Tool: {self.tool_name}\n", style="bold red")
        if self.reason:
            content.append(f"Reason: {self.reason}\n\n")
        if self.args:
            import json
            content.append("Arguments:\n")
            content.append(json.dumps(self.args, indent=2))

        return Panel(content, title="APPROVAL REQUIRED", border_style="red")

    def render_text(self, verbosity: int = 0) -> str:
        import json
        lines = [
            "APPROVAL REQUIRED",
            f"    Tool: {self.tool_name}",
        ]
        if self.reason:
            lines.append(f"    Reason: {self.reason}")
        if self.args:
            lines.append(f"    Args: {json.dumps(self.args)}")
        lines.append("    (Cannot approve in non-interactive mode)")
        return "\n".join(lines)

    def render_json(self) -> dict[str, Any]:
        return {
            "type": "approval_request",
            "worker": self.worker,
            "tool_name": self.tool_name,
            "reason": self.reason,
            "args": self.args,
        }

    def create_widget(self) -> "Widget":
        from llm_do.ui.widgets.messages import ApprovalMessage
        # Handle case where request is None by reconstructing from fields
        if self.request is None:
            from pydantic_ai_blocking_approval import ApprovalRequest
            self.request = ApprovalRequest(
                tool_name=self.tool_name,
                tool_args=self.args,
                description=self.reason,
            )
        return ApprovalMessage(self.request)
```

## Event Parsing

The event parser converts raw callback payloads into typed `UIEvent` instances. This is the **single place** where raw pydantic-ai event types are inspected.

```python
def _extract_delta_content(event: "PartDeltaEvent") -> str:
    """Safely extract content delta from a PartDeltaEvent.

    PartDeltaEvent.delta varies by part type, so we use a try/except
    rather than hasattr checks for cleaner code.
    """
    try:
        return event.delta.content_delta or ""
    except AttributeError:
        return ""


def parse_event(payload: dict[str, Any]) -> UIEvent:
    """Parse a raw callback payload into a typed UIEvent.

    This is the single point where raw pydantic-ai events and
    callback dicts are converted to our typed event hierarchy.
    """
    from pydantic_ai.messages import (
        FinalResultEvent,
        FunctionToolCallEvent,
        FunctionToolResultEvent,
        PartDeltaEvent,
        PartEndEvent,
        PartStartEvent,
        TextPart,
    )

    worker = payload.get("worker", "worker")

    # Initial request preview
    if "initial_request" in payload:
        req = payload["initial_request"]
        return InitialRequestEvent(
            worker=worker,
            instructions=req.get("instructions", ""),
            user_input=req.get("user_input", ""),
            attachments=req.get("attachments", []),
        )

    # Status update
    if "status" in payload:
        status = payload["status"]
        if isinstance(status, dict):
            return StatusEvent(
                worker=worker,
                phase=status.get("phase", ""),
                state=status.get("state", ""),
                model=status.get("model", ""),
                duration_sec=status.get("duration_sec"),
            )
        return StatusEvent(worker=worker, phase=str(status))

    # PydanticAI event
    event = payload.get("event")
    if event is None:
        return StatusEvent(worker=worker)  # Fallback for unknown payloads

    if isinstance(event, PartStartEvent):
        if isinstance(event.part, TextPart):
            return TextResponseEvent(worker=worker, is_complete=False)
        # Tool call start is handled by FunctionToolCallEvent
        return StatusEvent(worker=worker)

    if isinstance(event, PartDeltaEvent):
        # Safely extract content delta - PartDeltaEvent.delta may vary by part type
        delta = _extract_delta_content(event)
        return TextResponseEvent(worker=worker, content=delta, is_delta=True)

    if isinstance(event, PartEndEvent):
        if isinstance(event.part, TextPart):
            return TextResponseEvent(
                worker=worker,
                content=event.part.content,
                is_complete=True,
            )
        return StatusEvent(worker=worker)

    if isinstance(event, FunctionToolCallEvent):
        part = event.part
        return ToolCallEvent(
            worker=worker,
            tool_name=getattr(part, "tool_name", "tool"),
            tool_call_id=getattr(part, "tool_call_id", ""),
            args=getattr(part, "args", {}),
            args_json=part.args_as_json_str() if hasattr(part, "args_as_json_str") else "",
        )

    if isinstance(event, FunctionToolResultEvent):
        result = event.result
        return ToolResultEvent(
            worker=worker,
            tool_name=getattr(result, "tool_name", "tool"),
            tool_call_id=getattr(result, "tool_call_id", ""),
            content=str(result.content) if hasattr(result, "content") else str(result),
            is_error=getattr(result, "is_error", False),
        )

    if isinstance(event, FinalResultEvent):
        return CompletionEvent(worker=worker)

    # Unknown event type - return empty status
    return StatusEvent(worker=worker)
```

## Display Backends

With events knowing how to render themselves, backends become thin wrappers.

### DisplayBackend (Abstract Base)

```python
class DisplayBackend(ABC):
    """Interface for rendering UI events."""

    verbosity: int = 0

    async def start(self) -> None:
        """Called before event loop starts."""
        pass

    async def stop(self) -> None:
        """Called after event loop ends."""
        pass

    @abstractmethod
    def display(self, event: UIEvent) -> None:
        """Display a single event."""
        ...
```

### RichDisplayBackend

```python
class RichDisplayBackend(DisplayBackend):
    """Rich-formatted renderer using Rich Console."""

    def __init__(
        self,
        stream: TextIO | None = None,
        force_terminal: bool = False,
        verbosity: int = 0,
    ):
        from rich.console import Console

        self.stream = stream or sys.stderr
        self.verbosity = verbosity
        self.console = Console(
            file=self.stream,
            force_terminal=force_terminal,
            width=120,
        )

    def display(self, event: UIEvent) -> None:
        renderable = event.render_rich(self.verbosity)
        if renderable is not None:
            self.console.print(renderable)
```

### HeadlessDisplayBackend

```python
class HeadlessDisplayBackend(DisplayBackend):
    """Plain text renderer (ASCII only, no ANSI codes)."""

    def __init__(self, stream: TextIO | None = None, verbosity: int = 0):
        self.stream = stream or sys.stderr
        self.verbosity = verbosity

    def display(self, event: UIEvent) -> None:
        text = event.render_text(self.verbosity)
        if text is not None:
            self.stream.write(text + "\n")
            self.stream.flush()
```

### JsonDisplayBackend

```python
class JsonDisplayBackend(DisplayBackend):
    """JSONL renderer for automation/scripting."""

    def __init__(self, stream: TextIO | None = None):
        self.stream = stream or sys.stderr

    def display(self, event: UIEvent) -> None:
        import json
        record = event.render_json()
        json.dump(record, self.stream)
        self.stream.write("\n")
        self.stream.flush()
```

### TextualDisplayBackend

```python
class TextualDisplayBackend(DisplayBackend):
    """Forwards events to Textual TUI app via queue."""

    def __init__(self, event_queue: asyncio.Queue[UIEvent | None]):
        self._queue = event_queue

    def display(self, event: UIEvent) -> None:
        self._queue.put_nowait(event)
```

## Textual TUI Application

### LlmDoApp

Main Textual application class.

```python
from llm_do.ui.events import UIEvent, TextResponseEvent, ApprovalRequestEvent

class LlmDoApp(App[None]):
    """Main Textual application for llm-do TUI."""

    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1;
        grid-rows: 1fr auto auto;
    }

    MessageContainer {
        height: 100%;
        scrollbar-gutter: stable;
    }

    #input-container {
        height: auto;
        padding: 1;
        background: $surface;
    }

    #user-input {
        dock: bottom;
    }

    Footer {
        height: auto;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("a", "approve", "Approve", show=False),
        Binding("s", "approve_session", "Approve Session", show=False),
        Binding("d", "deny", "Deny", show=False),
    ]

    def __init__(
        self,
        event_queue: asyncio.Queue[UIEvent | None],  # Typed events, not Any
        approval_response_queue: asyncio.Queue[ApprovalDecision] | None = None,
        worker_coro: Coroutine[Any, Any, Any] | None = None,
        auto_quit: bool = True,
    ):
        super().__init__()
        self._event_queue = event_queue
        self._approval_response_queue = approval_response_queue
        self._worker_coro = worker_coro
        self._auto_quit = auto_quit
        self._pending_approval: ApprovalRequest | None = None
        self._worker_task: asyncio.Task[Any] | None = None
        self._done = False
        self._messages: list[str] = []
        self.final_result: str | None = None
```

**Constructor Parameters:**
- `event_queue`: Receives `UIEvent` instances from worker
- `approval_response_queue`: Sends `ApprovalDecision` back to worker
- `worker_coro`: Optional coroutine to run as background task
- `auto_quit`: Exit automatically when worker completes

**Instance State:**
- `_pending_approval`: Current `ApprovalRequest` awaiting response
- `_worker_task`: Background task running worker_coro
- `_done`: Boolean flag for completion
- `_messages`: List[str] capturing response text
- `final_result`: Joined messages for post-exit display

### Compose Method

```python
def compose(self) -> ComposeResult:
    yield Header(show_clock=True)
    yield MessageContainer(id="messages")
    yield Vertical(
        Input(placeholder="Enter message...", id="user-input", disabled=True),
        id="input-container",
    )
    yield Footer()
```

### Layout

Layout (top to bottom):
- Header (show_clock=True)
- MessageContainer (scrollable, grows 1fr, id="messages")
- Input (disabled, placeholder, id="user-input")
- Footer (key bindings)

### Lifecycle Methods

```python
async def on_mount(self) -> None:
    """Start the event consumer and worker when app mounts."""
    self._event_task = asyncio.create_task(self._consume_events())
    if self._worker_coro is not None:
        self._worker_task = asyncio.create_task(self._worker_coro)

async def on_unmount(self) -> None:
    """Clean up on unmount."""
    if hasattr(self, "_event_task"):
        self._event_task.cancel()
```

### Event Consumer Loop

The consumer is simple because MessageContainer handles rendering and streaming. No string discrimination or `hasattr` checks needed.

```python
async def _consume_events(self) -> None:
    """Consume events from the queue and update UI."""
    messages = self.query_one("#messages", MessageContainer)

    while not self._done:
        try:
            event = await asyncio.wait_for(
                self._event_queue.get(),
                timeout=0.1,
            )
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            break

        if event is None:
            # Sentinel - worker done
            self._done = True
            if self._messages:
                self.final_result = "\n".join(self._messages)
            if self._auto_quit:
                self.exit()
            else:
                messages.add_status("Press 'q' to exit")
            self._event_queue.task_done()
            break

        # Let MessageContainer handle streaming and widget mounting (with error handling)
        try:
            messages.handle_event(event)
        except Exception as e:
            # Log display errors but don't crash the UI
            messages.add_status(f"Display error: {e}")

        # Handle special cases that need app state management
        self._handle_event_state(event)

        self._event_queue.task_done()

def _handle_event_state(self, event: UIEvent) -> None:
    """Handle events that need app state management."""
    if isinstance(event, TextResponseEvent):
        if event.is_complete:
            # Capture complete response for final output
            self._messages.append(event.content)
    elif isinstance(event, ApprovalRequestEvent):
        # Store pending approval for action handlers
        self._pending_approval = event.request
```

**Key simplifications:**
1. **No string discrimination** - typed events replace `if event.kind == "..."` checks
2. **No hasattr checks** - we know the event type at compile time
3. **Single responsibility** - `MessageContainer` handles rendering/streaming, app handles state
4. **Type safety** - `isinstance` checks enable IDE autocompletion and type checking

### Action Methods (Approval Handling)

```python
def action_approve(self) -> None:
    """Handle 'a' key - approve once."""
    if self._pending_approval and self._approval_response_queue:
        self._approval_response_queue.put_nowait(ApprovalDecision(approved=True))
        self._pending_approval = None

def action_approve_session(self) -> None:
    """Handle 's' key - approve for session."""
    if self._pending_approval and self._approval_response_queue:
        self._approval_response_queue.put_nowait(
            ApprovalDecision(approved=True, remember="session")
        )
        self._pending_approval = None

def action_deny(self) -> None:
    """Handle 'd' key - deny."""
    if self._pending_approval and self._approval_response_queue:
        self._approval_response_queue.put_nowait(
            ApprovalDecision(approved=False, note="Rejected via TUI")
        )
        self._pending_approval = None

def signal_done(self) -> None:
    """Signal that the worker is done."""
    self._done = True
```

### Key Bindings

| Key | Action | Description |
|-----|--------|-------------|
| `q` | `action_quit` | Quit application |
| `a` | `action_approve` | Approve current tool once |
| `s` | `action_approve_session` | Approve tool for session |
| `d` | `action_deny` | Deny current tool |

**Note:** Approval bindings (`a`, `s`, `d`) have `show=False` since they only appear contextually when an approval is pending.

## Message Widgets

All widgets inherit from `BaseMessage(Static)`.

### BaseMessage

```python
class BaseMessage(Static):
    DEFAULT_CSS = """
    BaseMessage {
        width: 100%;
        padding: 1;
        margin: 0 0 1 0;
    }
    """
```

### AssistantMessage

For streaming/complete model responses.

```python
class AssistantMessage(BaseMessage):
    DEFAULT_CSS = """
    AssistantMessage {
        background: $primary-background;
        border: solid $primary;
    }
    """

    def __init__(self, content: str = "", **kwargs): ...
    def append_text(self, text: str) -> None:
        self._content += text
        self.update(self._content)
    def set_text(self, text: str) -> None:
        self._content = text
        self.update(self._content)
```

### ToolCallMessage

For tool invocations.

```python
class ToolCallMessage(BaseMessage):
    DEFAULT_CSS = """
    ToolCallMessage {
        background: $warning-darken-3;
        border: solid $warning;
    }
    """

    def __init__(self, tool_name: str, tool_call: Any, **kwargs): ...
```

**Display Format:**
```
[bold yellow]Tool: tool_name[/bold yellow]
Args: {"key": "value", ...}
```

### ToolResultMessage

For tool results.

```python
class ToolResultMessage(BaseMessage):
    DEFAULT_CSS = """
    ToolResultMessage {
        background: $success-darken-3;
        border: solid $success;
    }
    """

    def __init__(self, tool_name: str, result: Any, **kwargs): ...
```

**Display Format:**
```
[bold green]Result: tool_name[/bold green]
result content (truncated to 500 chars)
```

### StatusMessage

For status updates.

```python
class StatusMessage(BaseMessage):
    DEFAULT_CSS = """
    StatusMessage {
        color: $text-muted;
        padding: 0 1;
        margin: 0;
        background: transparent;
        border: none;
    }
    """
```

### ErrorMessage

For error display.

```python
class ErrorMessage(BaseMessage):
    DEFAULT_CSS = """
    ErrorMessage {
        background: $error-darken-3;
        border: solid $error;
    }
    """

    def __init__(self, message: str, error_type: str = "error", **kwargs):
        super().__init__(**kwargs)
        self._message = message
        self._error_type = error_type

    def compose(self) -> ComposeResult:
        from rich.text import Text
        content = Text(f"ERROR {self._error_type}: ", style="bold red")
        content.append(self._message)
        yield Static(content)
```

**Display Format:**
```
ERROR error_type: error message here
```

### ApprovalMessage

For interactive approval requests.

```python
class ApprovalMessage(BaseMessage):
    DEFAULT_CSS = """
    ApprovalMessage {
        background: $error-darken-3;
        border: solid $error;
    }
    """

    def __init__(self, request: ApprovalRequest, **kwargs): ...
```

**Display Format:**
```
[bold red]Approval Required: tool_name[/bold red]

Reason: description text

Arguments:
{
  "arg1": "value1"
}

[green][[a]][/green] Approve once
[green][[s]][/green] Approve for session
[red][[d]][/red] Deny
[red][[q]][/red] Quit
```

### MessageContainer

Scrollable container managing message widgets. Handles streaming and event routing for assistant messages.

```python
class MessageContainer(ScrollableContainer):
    """Scrollable container for all messages."""

    DEFAULT_CSS = """
    MessageContainer {
        height: 100%;
        padding: 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._current_assistant: AssistantMessage | None = None

    def start_assistant_message(self) -> AssistantMessage:
        """Start a new assistant message for streaming."""
        self._current_assistant = AssistantMessage()
        self.mount(self._current_assistant)
        self.scroll_end(animate=False)
        return self._current_assistant

    def append_to_assistant(self, text: str) -> None:
        """Append text to the current assistant message."""
        if self._current_assistant is None:
            self._current_assistant = self.start_assistant_message()
        self._current_assistant.append_text(text)
        self.scroll_end(animate=False)

    def finalize_assistant(self, content: str) -> AssistantMessage:
        """Finalize the assistant message with the full content."""
        if self._current_assistant is None:
            self._current_assistant = self.start_assistant_message()
        self._current_assistant.set_text(content)
        self.scroll_end(animate=False)
        return self._current_assistant

    def add_tool_call(self, tool_name: str, tool_call: Any) -> ToolCallMessage:
        """Add a tool call message."""
        self._current_assistant = None  # End any streaming
        msg = ToolCallMessage(tool_name, tool_call)
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def add_tool_result(self, tool_name: str, result: Any) -> ToolResultMessage:
        """Add a tool result message."""
        self._current_assistant = None  # End any streaming
        msg = ToolResultMessage(tool_name, result)
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def add_status(self, text: str) -> StatusMessage:
        """Add a status message."""
        msg = StatusMessage(f"[dim]{text}[/dim]")
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def add_approval_request(self, request: ApprovalRequest) -> ApprovalMessage:
        """Add an approval request message."""
        self._current_assistant = None  # End any streaming
        msg = ApprovalMessage(request)
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def handle_event(self, event: UIEvent) -> None:
        """Route events to the right widget/streaming handler."""
        from llm_do.ui.events import (
            ApprovalRequestEvent,
            ErrorEvent,
            TextResponseEvent,
            ToolCallEvent,
            ToolResultEvent,
        )

        if isinstance(event, TextResponseEvent):
            if event.is_delta:
                self.append_to_assistant(event.content)
            elif event.is_complete:
                self.finalize_assistant(event.content)
            else:
                self.start_assistant_message()
            return

        if isinstance(event, (ToolCallEvent, ToolResultEvent, ApprovalRequestEvent, ErrorEvent)):
            self._current_assistant = None  # Interrupt streaming

        widget = event.create_widget()
        if widget is not None:
            self.mount(widget)
            self.scroll_end(animate=False)
```

**Key behaviors:**
- `_current_assistant` tracks the active streaming message
- `handle_event` routes streaming deltas/completions, uses `finalize_assistant` for the full response, and interrupts streaming for tool/approval/error events
- All add/finalize methods auto-scroll via `scroll_end(animate=False)`

## CLI Integration

**Key insight:** Parsing happens in the message callback, before events are queued. This means:
- The queue always contains typed `UIEvent` instances
- Consumers (TUI, Rich, Headless) never see raw payloads
- All pydantic-ai type inspection is centralized in `parse_event()`

### TUI Mode Flow

TUI mode uses two buffers to capture output during execution, then prints to the correct streams after exit. Verbosity controls what gets captured in the events buffer.

```python
from llm_do.ui.parser import parse_event
from llm_do.ui.events import UIEvent, TextResponseEvent
import sys

async def _run_tui_mode(args):
    # 1. Create queues (typed!)
    event_queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    approval_queue: asyncio.Queue[ApprovalDecision] = asyncio.Queue()

    # 2. Create backends - TUI for interactive display
    tui_backend = TextualDisplayBackend(event_queue)

    # 3. Create DUAL buffers for post-TUI output
    events_buffer = io.StringIO()   # Will go to stderr
    result_buffer = io.StringIO()   # Will go to stdout

    # Verbosity controls what events are captured
    rich_backend = RichDisplayBackend(
        stream=events_buffer,
        force_terminal=True,
        verbosity=args.verbosity,  # 0=minimal, 1=normal, 2=verbose
    )

    # 4. Create combined message callback that parses events
    def combined_callback(raw_events):
        for raw_event in raw_events:
            ui_event = parse_event(raw_event)
            tui_backend.display(ui_event)
            rich_backend.display(ui_event)  # Respects verbosity
            # Capture final result separately
            if isinstance(ui_event, TextResponseEvent) and ui_event.is_complete:
                result_buffer.write(ui_event.content)

    # 5. Run worker as background coroutine
    async def run_worker():
        result = await run_worker_async(..., message_callback=combined_callback)
        event_queue.put_nowait(None)  # Sentinel
        return result

    # 6. Create and run TUI app
    app = LlmDoApp(event_queue, approval_queue, worker_coro=run_worker())
    await app.run_async(mouse=False)

    # 7. Print captured output to correct streams after TUI exits
    sys.stderr.write(events_buffer.getvalue())  # Events -> stderr
    sys.stdout.write(result_buffer.getvalue())  # Result -> stdout
```

**Future consideration:** Replace direct stderr writes with Python's `logging` module:
- Built-in level filtering (DEBUG/INFO/WARNING maps to verbosity)
- Configurable handlers (file, syslog, structured JSON)
- Standard pattern for library code
- Users could configure via `logging.basicConfig()` or config file

### Headless/Rich Mode Flow

Events go directly to stderr with verbosity filtering. Final result goes to stdout.

```python
import sys

async def _run_headless_mode(args):
    # 1. Create queue and backend (writes to stderr)
    queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    if args.rich:
        backend = RichDisplayBackend(
            stream=sys.stderr,
            force_terminal=True,
            verbosity=args.verbosity,
        )
    else:
        backend = HeadlessDisplayBackend(
            stream=sys.stderr,
            verbosity=args.verbosity,
        )

    # 2. Start render loop
    renderer = asyncio.create_task(_render_loop(queue, backend))

    # 3. Create callback that parses events
    def callback(raw_events):
        for raw_event in raw_events:
            ui_event = parse_event(raw_event)
            queue.put_nowait(ui_event)

    # 4. Run worker
    result = await run_worker_async(..., message_callback=callback)

    # 5. Signal completion and wait for renderer
    await queue.put(None)
    await renderer

    # 6. Print final result to stdout (pipeable)
    sys.stdout.write(result.output)
```

### Render Loop

```python
async def _render_loop(queue: asyncio.Queue[UIEvent | None], backend: DisplayBackend):
    await backend.start()
    try:
        while True:
            event = await queue.get()
            if event is None:
                queue.task_done()
                break
            backend.display(event)  # Respects verbosity internally
            queue.task_done()
    finally:
        await backend.stop()
```

## Approval Flow

### Interactive (TUI)

1. Worker calls tool requiring approval
2. Approval callback creates `ApprovalRequestEvent` and queues it
3. TUI displays `ApprovalMessage` widget (via `event.create_widget()`)
4. User presses key (a/s/d/q)
5. Action handler queues `ApprovalDecision` to `approval_response_queue`
6. Worker receives decision, continues or aborts

### Non-Interactive

Requires `--approve-all` or `--strict` flag:
- `--approve-all`: All tools auto-approved
- `--strict`: All non-pre-approved tools rejected

## File Structure

```
llm_do/ui/
|-- __init__.py          # Public exports
|-- events.py            # UIEvent base class and all subclasses
|-- parser.py            # parse_event() function
|-- display.py           # DisplayBackend and implementations
|-- app.py               # LlmDoApp Textual application
`-- widgets/
    `-- messages.py      # Message widget classes
```

## Rendering Constants Reference

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_INPUT_DISPLAY` | 200 | Truncate user input display |
| `MAX_ARGS_DISPLAY` | 200 | Truncate tool arguments display |
| `MAX_RESULT_DISPLAY` | 500 | Truncate tool result length |
| `MAX_RESULT_LINES` | 10 | Truncate tool result line count |

## Verbosity Levels Reference

| Level | Name | Shows |
|-------|------|-------|
| 0 | minimal | Prompts, responses, tool calls/results, status |
| 1 | normal | + "Generating...", "Complete" indicators |
| 2 | verbose | + Streaming deltas as they arrive |

## Dependencies

- **textual** - TUI framework
- **rich** - Terminal formatting
- **pydantic-ai** - Source event types (only used in parser)
- **pydantic-ai-blocking-approval** - Approval types

## External Types (from pydantic-ai-blocking-approval)

The approval system uses types from the `pydantic_ai_blocking_approval` package. These are Pydantic models that flow between the worker execution and UI layers.

### ApprovalRequest

Created by `ApprovalToolset` when a tool call needs user approval. Passed to the UI via `ApprovalRequestEvent`.

```python
from pydantic_ai_blocking_approval import ApprovalRequest

class ApprovalRequest(BaseModel):
    """Request for user approval before executing a tool."""

    tool_name: str
    """Name of the tool requesting approval (e.g., 'shell', 'write_file')."""

    tool_args: dict[str, Any]
    """Arguments passed to the tool. Used for display and session cache matching."""

    description: str
    """Human-readable description of what the tool wants to do.
    Generated by the tool's `approval_description()` method."""
```

**Example:**
```python
ApprovalRequest(
    tool_name="shell",
    tool_args={"command": "rm -rf /tmp/cache"},
    description="Execute shell command: rm -rf /tmp/cache"
)
```

### ApprovalDecision

Returned by the UI after the user (or auto-mode) decides whether to approve a tool operation.

```python
from pydantic_ai_blocking_approval import ApprovalDecision

class ApprovalDecision(BaseModel):
    """User's decision about a tool call."""

    approved: bool
    """Whether the operation should proceed."""

    note: Optional[str] = None
    """Optional reason for rejection or comment."""

    remember: Literal['none', 'session'] = 'none'
    """Whether to cache this decision:
    - 'none': Don't remember (ask again next time)
    - 'session': Remember for this tool+args combo for the session
    """
```

**Example decisions:**
```python
# Approve once
ApprovalDecision(approved=True)

# Approve for session (pressing 's' in TUI)
ApprovalDecision(approved=True, remember='session')

# Deny with reason
ApprovalDecision(approved=False, note="Command looks dangerous")
```

### Approval Flow Diagram

Approval flow (top to bottom):
- Tool Execution Layer: ApprovalToolset wraps tool, checks if approval needed
- ApprovalRequest: tool_name="shell", tool_args={"command": "rm -rf /tmp/cache"}, description="Execute shell command: rm -rf /tmp/cache"
- UI Layer: TUI shows ApprovalMessage widget, Headless auto-approve (--approve-all) or reject (--strict)
- ApprovalDecision: approved=True/False, remember="session" when requested
- Tool Execution Continues/Aborts: approved executes, denied raises ToolDeniedError, session decisions are cached

### Import Pattern

```python
# In UI code
from pydantic_ai_blocking_approval import ApprovalRequest, ApprovalDecision

# These are also re-exported from llm_do.base for convenience
from llm_do.base import ApprovalDecision
```

## CLI Flags Reference

| Flag | Effect |
|------|--------|
| (default) | TUI mode, captures to Rich buffer, prints on exit |
| `--headless` | Plain text output to stderr |
| `--no-rich` | Disable Rich formatting (plain text, no colors) |
| `--json` | JSONL output to stderr, JSON result to stdout |
| `--approve-all` | Auto-approve all tools (required for non-interactive) |
| `--strict` | Reject all non-pre-approved tools (required for non-interactive) |

## Implementation Status

This spec is implemented in the current codebase. The checklist below is a
status snapshot; remaining items are mostly tests.

### Phase 1: Core Event System
- [x] Create `llm_do/ui/events.py` with:
  - [x] `UIEvent` base class with abstract render methods
  - [x] `InitialRequestEvent`
  - [x] `StatusEvent`
  - [x] `TextResponseEvent`
  - [x] `ToolCallEvent`
  - [x] `ToolResultEvent`
  - [x] `DeferredToolEvent`
  - [x] `CompletionEvent`
  - [x] `ErrorEvent`
  - [x] `ApprovalRequestEvent`

### Phase 2: Parser
- [x] Create `llm_do/ui/parser.py` with:
  - [x] `_extract_delta_content()` helper
  - [x] `parse_event()` function
  - [ ] Unit tests for each event type conversion

### Phase 3: Display Backends
- [x] Create/update `llm_do/ui/display.py` with:
  - [x] `DisplayBackend` abstract base class
  - [x] `RichDisplayBackend`
  - [x] `HeadlessDisplayBackend`
  - [x] `JsonDisplayBackend`
  - [x] `TextualDisplayBackend`

### Phase 4: Widgets
- [x] Create/update `llm_do/ui/widgets/messages.py` with:
  - [x] `BaseMessage`
  - [x] `AssistantMessage` (with `append_text()`)
  - [x] `ToolCallMessage`
  - [x] `ToolResultMessage`
  - [x] `StatusMessage`
  - [x] `ErrorMessage`
  - [x] `ApprovalMessage`
  - [x] `MessageContainer`

### Phase 5: TUI Application
- [x] Update `llm_do/ui/app.py`:
  - [x] Remove `_handle_runtime_event()` method
  - [x] Remove `_handle_dict_event()` method
  - [x] Remove `_handle_deferred_tool()` method
  - [x] Remove all `if event.kind == "..."` branching
  - [x] Remove all `hasattr()` checks for payload inspection
  - [x] Implement typed `_consume_events()` loop
  - [x] Add `_handle_event_state()` for special state management
  - [x] Add error handling around `event.create_widget()`

### Phase 6: CLI Integration
- [x] Update CLI to use `parse_event()` in message callbacks
- [x] Verify TUI mode captures to buffers correctly
- [x] Verify headless/rich modes write to stderr
- [x] Verify final result goes to stdout

### Phase 7: Testing
- [ ] Unit tests for each event's `render_rich()` method
- [ ] Unit tests for each event's `render_text()` method
- [ ] Unit tests for each event's `render_json()` method
- [ ] Unit tests for each event's `create_widget()` method
- [ ] Integration test: TUI mode end-to-end
- [ ] Integration test: Headless mode end-to-end
- [ ] Integration test: Rich mode end-to-end
- [ ] Integration test: JSON mode end-to-end
- [ ] Integration test: Approval flow in TUI
- [ ] Integration test: Error handling display
