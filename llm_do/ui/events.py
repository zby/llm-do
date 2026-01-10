"""Typed UI event classes for llm-do.

Each event knows how to render itself in multiple formats, following the
"Events Know How to Render Themselves" principle.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from pydantic_ai_blocking_approval import ApprovalRequest
    from rich.console import RenderableType
    from textual.widget import Widget


@dataclass
class UIEvent(ABC):
    """Base class for all UI events.

    Each event knows how to render itself in multiple formats.
    The render methods receive context (verbosity) as parameters.
    """

    worker: str = ""
    depth: int = 0

    @property
    def worker_tag(self) -> str:
        """Format worker and depth as a tag like [worker:depth]."""
        return f"[{self.worker}:{self.depth}]"

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


@dataclass
class InitialRequestEvent(UIEvent):
    """Event emitted when worker receives initial request."""

    instructions: str = ""
    user_input: str = ""
    attachments: list[str] = field(default_factory=list)

    MAX_INPUT_DISPLAY: ClassVar[int] = 200
    MAX_INSTRUCTIONS_DISPLAY: ClassVar[int] = 400

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.console import Group
        from rich.text import Text

        parts = [Text(f"[{self.worker}] ", style="bold cyan") + Text("Starting...")]
        if self.instructions:
            display_instructions = self._truncate(
                self.instructions, self.MAX_INSTRUCTIONS_DISPLAY
            )
            parts.append(Text("  Instructions: ", style="dim") + Text(display_instructions))
        if self.user_input:
            display_input = self._truncate(self.user_input, self.MAX_INPUT_DISPLAY)
            parts.append(Text("  Prompt: ", style="dim") + Text(display_input))
        if self.attachments:
            parts.append(
                Text("  Attachments: ", style="dim")
                + Text(", ".join(self.attachments))
            )
        return Group(*parts)

    def render_text(self, verbosity: int = 0) -> str:
        lines = [f"[{self.worker}] Starting..."]
        if self.instructions:
            display_instructions = self._truncate(
                self.instructions, self.MAX_INSTRUCTIONS_DISPLAY
            )
            lines.append(f"  Instructions: {display_instructions}")
        if self.user_input:
            display_input = self._truncate(self.user_input, self.MAX_INPUT_DISPLAY)
            lines.append(f"  Prompt: {display_input}")
        if self.attachments:
            lines.append(f"  Attachments: {', '.join(self.attachments)}")
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


@dataclass
class StatusEvent(UIEvent):
    """Event emitted for phase/state transitions."""

    phase: str = ""
    state: str = ""
    model: str = ""
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

    def create_widget(self) -> "Widget | None":
        from llm_do.ui.widgets.messages import StatusMessage

        if not self.phase:
            return None
        text = f"{self.phase} {self.state}"
        if self.model:
            text += f" ({self.model})"
        return StatusMessage(text)


@dataclass
class UserMessageEvent(UIEvent):
    """Event emitted for user-submitted messages."""

    content: str = ""

    def render_rich(self, verbosity: int = 0) -> "RenderableType | None":
        from rich.text import Text

        return Text(f"[{self.worker}] You: {self.content}")

    def render_text(self, verbosity: int = 0) -> str | None:
        return f"[{self.worker}] You: {self.content}"

    def render_json(self) -> dict[str, Any]:
        return {
            "type": "user_message",
            "worker": self.worker,
            "content": self.content,
        }

    def create_widget(self) -> "Widget":
        from llm_do.ui.widgets.messages import UserMessage

        return UserMessage(self.content)


@dataclass
class TextResponseEvent(UIEvent):
    """Event emitted for model text responses."""

    content: str = ""
    is_complete: bool = True
    is_delta: bool = False

    def render_rich(self, verbosity: int = 0) -> "RenderableType | None":
        from rich.console import Group
        from rich.text import Text

        # Streaming deltas only shown at verbosity >= 2
        if self.is_delta:
            if verbosity >= 2:
                return Text(self.content, end="")
            return None

        # Complete responses
        if self.is_complete:
            header = (
                Text(f"\n{self.worker_tag} ", style="bold green")
                + Text("Response:")
            )
            content = Text("\n".join(f"  {line}" for line in self.content.split("\n")))
            return Group(header, content)

        # Start of streaming (verbosity >= 1)
        if verbosity >= 1:
            return (
                Text(f"{self.worker_tag} ", style="dim")
                + Text("Generating response...", style="dim")
            )
        return None

    def render_text(self, verbosity: int = 0) -> str | None:
        if self.is_delta:
            return self.content if verbosity >= 2 else None
        if self.is_complete:
            lines = [f"\n{self.worker_tag} Response:"]
            lines.extend(f"  {line}" for line in self.content.split("\n"))
            return "\n".join(lines)
        if verbosity >= 1:
            return f"{self.worker_tag} Generating response..."
        return None

    def render_json(self) -> dict[str, Any]:
        return {
            "type": "text_response",
            "worker": self.worker,
            "content": self.content,
            "depth": self.depth,
            "is_complete": self.is_complete,
            "is_delta": self.is_delta,
        }

    def create_widget(self) -> "Widget | None":
        # TUI handles streaming and finalization via MessageContainer
        return None


@dataclass
class ToolCallEvent(UIEvent):
    """Event emitted when a tool is called."""

    tool_name: str = ""
    tool_call_id: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    args_json: str = ""

    MAX_ARGS_DISPLAY: ClassVar[int] = 400

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.console import Group
        from rich.text import Text

        header = (
            Text(f"\n{self.worker_tag} ", style="bold yellow")
            + Text("Tool call: ")
            + Text(self.tool_name, style="yellow")
        )
        parts: list[Text] = [header]
        if self.args or self.args_json:
            args_str = self.args_json or str(self.args)
            args_display = self._truncate(args_str, self.MAX_ARGS_DISPLAY)
            parts.append(Text("  Args: ", style="dim") + Text(args_display))
        return Group(*parts)

    def render_text(self, verbosity: int = 0) -> str:
        lines = [f"\n{self.worker_tag} Tool call: {self.tool_name}"]
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

        # Pass both args and args_json so widget can use same logic as render_rich
        return ToolCallMessage(
            self.tool_name, self.args, self.args_json, self.worker_tag
        )

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        return text[:max_len] + "..." if len(text) > max_len else text


@dataclass
class ToolResultEvent(UIEvent):
    """Event emitted when a tool returns a result."""

    tool_name: str = ""
    tool_call_id: str = ""
    content: Any = ""  # Preserves structured data for JSON output
    is_error: bool = False

    MAX_RESULT_DISPLAY: ClassVar[int] = 500
    MAX_RESULT_LINES: ClassVar[int] = 10

    def _content_as_str(self) -> str:
        """Convert content to string for display."""
        import json

        if isinstance(self.content, str):
            return self.content
        try:
            return json.dumps(self.content, indent=2, default=str)
        except (TypeError, ValueError):
            return str(self.content)

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.console import Group
        from rich.text import Text

        style = "red" if self.is_error else "blue"
        label = "Tool error" if self.is_error else "Tool result"
        header = (
            Text(f"\n[{self.worker}] ", style=f"bold {style}")
            + Text(f"{label}: ")
            + Text(self.tool_name, style=style)
        )

        content_display = self._truncate_content(self._content_as_str())
        content_lines = [Text(f"  {line}") for line in content_display.split("\n")]

        return Group(header, *content_lines)

    def render_text(self, verbosity: int = 0) -> str:
        label = "Tool error" if self.is_error else "Tool result"
        lines = [f"\n[{self.worker}] {label}: {self.tool_name}"]
        content_display = self._truncate_content(self._content_as_str())
        lines.extend(f"  {line}" for line in content_display.split("\n"))
        return "\n".join(lines)

    def render_json(self) -> dict[str, Any]:
        return {
            "type": "tool_result",
            "worker": self.worker,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "content": self.content,  # Preserved as structured data
            "is_error": self.is_error,
        }

    def create_widget(self) -> "Widget":
        from llm_do.ui.widgets.messages import ToolResultMessage

        return ToolResultMessage(self.tool_name, self._content_as_str(), self.is_error)

    def _truncate_content(self, text: str) -> str:
        """Truncate content by both length and line count."""
        if len(text) > self.MAX_RESULT_DISPLAY:
            text = text[: self.MAX_RESULT_DISPLAY] + "..."
        lines = text.split("\n")
        if len(lines) > self.MAX_RESULT_LINES:
            remaining = len(lines) - self.MAX_RESULT_LINES
            text = "\n".join(lines[: self.MAX_RESULT_LINES]) + f"\n... ({remaining} more lines)"
        return text


@dataclass
class DeferredToolEvent(UIEvent):
    """Event emitted for deferred (async) tool status updates."""

    tool_name: str = ""
    status: str = ""

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.text import Text

        status_style = {
            "pending": "dim",
            "running": "yellow",
            "complete": "green",
            "error": "red",
        }.get(self.status, "")

        return (
            Text("  Deferred tool '")
            + Text(self.tool_name, style="yellow")
            + Text("': ")
            + Text(self.status, style=status_style)
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


@dataclass
class CompletionEvent(UIEvent):
    """Event emitted when worker completes successfully."""

    def render_rich(self, verbosity: int = 0) -> "RenderableType | None":
        from rich.text import Text

        if verbosity >= 1:
            return (
                Text(f"[{self.worker}] ", style="dim")
                + Text("[OK] Complete", style="green")
            )
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
        # Completion is handled at app level
        return None


@dataclass
class ErrorEvent(UIEvent):
    """Event emitted when an error occurs."""

    message: str = ""
    error_type: str = ""
    traceback: str | None = None

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.panel import Panel
        from rich.text import Text

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


@dataclass
class ApprovalRequestEvent(UIEvent):
    """Event emitted when tool requires user approval."""

    tool_name: str = ""
    reason: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    request: "ApprovalRequest | None" = None

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        import json

        from rich.panel import Panel
        from rich.text import Text

        content = Text()
        content.append(f"Tool: {self.tool_name}\n", style="bold red")
        if self.reason:
            content.append(f"Reason: {self.reason}\n\n")
        if self.args:
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

    def create_widget(self) -> "Widget | None":
        return None
