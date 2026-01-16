"""Typed UI event classes for llm-do."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from .formatting import truncate_lines, truncate_text

if TYPE_CHECKING:
    from pydantic_ai_blocking_approval import ApprovalRequest
    from rich.console import RenderableType
    from rich.text import Text
    from textual.widget import Widget


def _rich_text(*parts: tuple[str, str | None]) -> "Text":
    from rich.text import Text
    text = Text()
    for content, style in parts:
        if style:
            text.append(content, style=style)
        else:
            text.append(content)
    return text


def _rich_label_value(label: str, value: str, label_style: str = "dim") -> "Text":
    return _rich_text((label, label_style), (value, None))


@dataclass
class UIEvent(ABC):
    """Base class for all UI events."""

    worker: str = ""
    depth: int = 0

    @property
    def worker_tag(self) -> str:
        return f"[{self.worker}:{self.depth}]"

    @abstractmethod
    def render_rich(self, verbosity: int = 0) -> "RenderableType | None": ...

    @abstractmethod
    def render_text(self, verbosity: int = 0) -> str | None: ...

    @abstractmethod
    def create_widget(self) -> "Widget | None": ...


@dataclass
class InitialRequestEvent(UIEvent):
    """Event emitted when worker receives initial request."""
    instructions: str = ""
    user_input: str = ""
    attachments: list[str] = field(default_factory=list)
    MAX_INPUT_DISPLAY: ClassVar[int] = 200
    MAX_INSTRUCTIONS_DISPLAY: ClassVar[int] = 400

    def _detail_items(self) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        if self.instructions:
            items.append(
                (
                    "Instructions",
                    truncate_text(self.instructions, self.MAX_INSTRUCTIONS_DISPLAY),
                )
            )
        if self.user_input:
            items.append(("Prompt", truncate_text(self.user_input, self.MAX_INPUT_DISPLAY)))
        if self.attachments:
            items.append(("Attachments", ", ".join(self.attachments)))
        return items

    def _build_lines(self) -> list[str]:
        lines = [f"{self.worker_tag} Starting..."]
        for label, value in self._detail_items():
            lines.append(f"  {label}: {value}")
        return lines

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.console import Group
        parts = [_rich_text((f"{self.worker_tag} ", "bold cyan"), ("Starting...", None))]
        for label, value in self._detail_items():
            parts.append(_rich_label_value(f"  {label}: ", value))
        return Group(*parts)

    def render_text(self, verbosity: int = 0) -> str:
        return "\n".join(self._build_lines())

    def create_widget(self) -> "Widget":
        from llm_do.ui.widgets.messages import StatusMessage
        return StatusMessage(f"Starting: {truncate_text(self.user_input, 100)}")


@dataclass
class StatusEvent(UIEvent):
    """Event emitted for phase/state transitions."""
    phase: str = ""
    state: str = ""
    model: str = ""
    duration_sec: float | None = None

    def _format(self, with_tag: bool = True) -> str | None:
        if not self.phase:
            return None
        parts = [f"{self.worker_tag} " if with_tag else "", f"{self.phase} {self.state}"]
        if self.model:
            parts.append(f" ({self.model})")
        if self.duration_sec is not None:
            parts.append(f" [{self.duration_sec:.2f}s]")
        return "".join(parts)

    def render_rich(self, verbosity: int = 0) -> "RenderableType | None":
        if not self.phase:
            return None
        text = _rich_text((f"{self.worker_tag} ", "dim"), (f"{self.phase} {self.state}", None))
        if self.model:
            text.append(f" ({self.model})", style="dim")
        if self.duration_sec is not None:
            text.append(f" [{self.duration_sec:.2f}s]", style="dim")
        return text

    def render_text(self, verbosity: int = 0) -> str | None:
        return self._format()

    def create_widget(self) -> "Widget | None":
        from llm_do.ui.widgets.messages import StatusMessage
        text = self._format(with_tag=False)
        return StatusMessage(text) if text else None


@dataclass
class UserMessageEvent(UIEvent):
    """Event emitted for user-submitted messages."""
    content: str = ""

    def render_rich(self, verbosity: int = 0) -> "RenderableType | None":
        from rich.text import Text
        return Text(self.render_text(verbosity) or "")

    def render_text(self, verbosity: int = 0) -> str | None:
        return f"{self.worker_tag} You: {self.content}"

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

    def _args_display(self) -> str | None:
        if not (self.args or self.args_json):
            return None
        return truncate_text(self.args_json or str(self.args), self.MAX_ARGS_DISPLAY)

    def _build_lines(self) -> list[str]:
        lines = [f"\n{self.worker_tag} Tool call: {self.tool_name}"]
        args_display = self._args_display()
        if args_display:
            lines.append(f"  Args: {args_display}")
        return lines

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.console import Group
        header = _rich_text(
            (f"\n{self.worker_tag} ", "bold yellow"),
            ("Tool call: ", None),
            (self.tool_name, "yellow"),
        )
        parts = [header]
        args_display = self._args_display()
        if args_display:
            parts.append(_rich_label_value("  Args: ", args_display))
        return Group(*parts)

    def render_text(self, verbosity: int = 0) -> str:
        return "\n".join(self._build_lines())

    def create_widget(self) -> "Widget":
        from llm_do.ui.widgets.messages import ToolCallMessage
        return ToolCallMessage(self.tool_name, self.args, self.args_json, self.worker_tag)


@dataclass
class ToolResultEvent(UIEvent):
    """Event emitted when a tool returns a result."""
    tool_name: str = ""
    tool_call_id: str = ""
    content: Any = ""
    is_error: bool = False
    MAX_RESULT_DISPLAY: ClassVar[int] = 500
    MAX_RESULT_LINES: ClassVar[int] = 10

    def _content_as_str(self) -> str:
        import json
        if isinstance(self.content, str):
            return self.content
        try:
            return json.dumps(self.content, indent=2, default=str)
        except (TypeError, ValueError):
            return str(self.content)

    def _content_lines(self) -> list[str]:
        return truncate_lines(
            self._content_as_str(),
            self.MAX_RESULT_DISPLAY,
            self.MAX_RESULT_LINES,
        ).split("\n")

    def _build_lines(self) -> list[str]:
        label = "Tool error" if self.is_error else "Tool result"
        lines = [f"\n{self.worker_tag} {label}: {self.tool_name}"]
        lines.extend(f"  {line}" for line in self._content_lines())
        return lines

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        from rich.console import Group
        style = "red" if self.is_error else "blue"
        label = "Tool error" if self.is_error else "Tool result"
        header = _rich_text(
            (f"\n{self.worker_tag} ", f"bold {style}"),
            (f"{label}: ", None),
            (self.tool_name, style),
        )
        parts = [header]
        parts.extend(_rich_text((f"  {line}", None)) for line in self._content_lines())
        return Group(*parts)

    def render_text(self, verbosity: int = 0) -> str:
        return "\n".join(self._build_lines())

    def create_widget(self) -> "Widget":
        from llm_do.ui.widgets.messages import ToolResultMessage
        return ToolResultMessage(self.tool_name, self._content_as_str(), self.is_error, self.worker_tag)


@dataclass
class DeferredToolEvent(UIEvent):
    """Event emitted for deferred (async) tool status updates."""
    tool_name: str = ""
    status: str = ""

    def render_rich(self, verbosity: int = 0) -> "RenderableType":
        status_style = {
            "pending": "dim",
            "running": "yellow",
            "complete": "green",
            "error": "red",
        }.get(self.status, "")
        return _rich_text(
            ("  Deferred tool '", None),
            (self.tool_name, "yellow"),
            ("': ", None),
            (self.status, status_style),
        )

    def render_text(self, verbosity: int = 0) -> str:
        return f"  Deferred tool '{self.tool_name}': {self.status}"

    def create_widget(self) -> "Widget":
        from llm_do.ui.widgets.messages import StatusMessage
        return StatusMessage(self.render_text())


@dataclass
class CompletionEvent(UIEvent):
    """Event emitted when worker completes successfully."""

    def render_rich(self, verbosity: int = 0) -> "RenderableType | None":
        if verbosity >= 1:
            return _rich_text((f"{self.worker_tag} ", "dim"), ("[OK] Complete", "green"))
        return None

    def render_text(self, verbosity: int = 0) -> str | None:
        return f"{self.worker_tag} [OK] Complete" if verbosity >= 1 else None

    def create_widget(self) -> "Widget | None":
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
        lines = [f"{self.worker_tag} ERROR ({self.error_type}): {self.message}"]
        if verbosity >= 2 and self.traceback:
            lines.append(self.traceback)
        return "\n".join(lines)

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
        content = Text(f"Tool: {self.tool_name}\n", style="bold red")
        if self.reason:
            content.append(f"Reason: {self.reason}\n\n")
        if self.args:
            content.append(f"Arguments:\n{json.dumps(self.args, indent=2)}")
        return Panel(content, title="APPROVAL REQUIRED", border_style="red")

    def render_text(self, verbosity: int = 0) -> str:
        import json
        lines = ["APPROVAL REQUIRED", f"    Tool: {self.tool_name}"]
        if self.reason:
            lines.append(f"    Reason: {self.reason}")
        if self.args:
            lines.append(f"    Args: {json.dumps(self.args)}")
        lines.append("    (Cannot approve in non-interactive mode)")
        return "\n".join(lines)

    def create_widget(self) -> "Widget | None":
        return None
