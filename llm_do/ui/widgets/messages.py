"""Message display widgets for the Textual TUI."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic_ai_blocking_approval import ApprovalRequest
from textual.containers import ScrollableContainer
from textual.widgets import Static

from llm_do.ui.events import ToolCallEvent, ToolResultEvent

if TYPE_CHECKING:
    from llm_do.ui.events import UIEvent


_TRUNCATION_INDICATOR = "… [truncated]."


def _truncate_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + _TRUNCATION_INDICATOR


class BaseMessage(Static):
    """Base class for all message widgets."""

    DEFAULT_CSS = """
    BaseMessage {
        width: 100%;
        padding: 1;
        margin: 0 0 1 0;
    }
    """


class AssistantMessage(BaseMessage):
    """Widget for displaying assistant/model responses."""

    DEFAULT_CSS = """
    AssistantMessage {
        background: $primary-background;
        border: solid $primary;
    }
    """

    def __init__(self, content: str = "", **kwargs: Any) -> None:
        super().__init__(content, markup=False, **kwargs)
        self._content = content

    def append_text(self, text: str) -> None:
        """Append streaming text to this message."""
        self._content += text
        self.update(self._content)

    def set_text(self, text: str) -> None:
        """Set the full text content of this message."""
        self._content = text
        self.update(self._content)


class UserMessage(BaseMessage):
    """Widget for displaying user input."""

    DEFAULT_CSS = """
    UserMessage {
        background: $surface;
        border: solid $secondary;
    }
    """

    def __init__(self, content: str = "", **kwargs: Any) -> None:
        super().__init__(content, markup=False, **kwargs)


class ToolCallMessage(BaseMessage):
    """Widget for displaying tool calls."""

    DEFAULT_CSS = """
    ToolCallMessage {
        background: $warning-darken-3;
        border: solid $warning;
    }
    """

    def __init__(
        self,
        tool_name: str,
        tool_call: Any,
        args_json: str = "",
        worker: str = "",
        depth: int = 0,
        **kwargs: Any,
    ) -> None:
        self._tool_name = tool_name
        self._tool_call = tool_call
        self._args_json = args_json
        self._worker = worker
        self._depth = depth

        # Format the tool call for display
        content = self._format_tool_call()
        super().__init__(content, markup=False, **kwargs)

    def _format_tool_call(self) -> str:
        """Format tool call for display."""
        if self._worker:
            lines = [f"[{self._worker}:{self._depth}] Tool: {self._tool_name}"]
        else:
            lines = [f"Tool: {self._tool_name}"]

        # Handle both dict args and objects with .args attribute
        args: Any | None
        if isinstance(self._tool_call, dict):
            args = self._tool_call
        elif hasattr(self._tool_call, "args"):
            args = self._tool_call.args
        else:
            args = None

        # Use same logic as render_rich: prefer args_json, fallback to args
        if args or self._args_json:
            # TODO: support semantic tool renderers (see docs/notes/tool-output-rendering-semantics.md).
            if self._args_json:
                args_str = self._args_json
            elif isinstance(args, dict):
                args_str = json.dumps(args, indent=2, default=str)
            else:
                args_str = str(args)
            args_str = _truncate_text(args_str, ToolCallEvent.MAX_ARGS_DISPLAY)
            lines.append(f"Args: {args_str}")

        return "\n".join(lines)


class ToolResultMessage(BaseMessage):
    """Widget for displaying tool results."""

    DEFAULT_CSS = """
    ToolResultMessage {
        background: $success-darken-3;
        border: solid $success;
    }
    ToolResultMessage.error {
        background: $error-darken-3;
        border: solid $error;
    }
    """

    def __init__(self, tool_name: str, result: Any, is_error: bool = False, **kwargs: Any) -> None:
        self._tool_name = tool_name
        self._result = result
        self._is_error = is_error

        content = self._format_result()
        super().__init__(content, markup=False, **kwargs)
        if is_error:
            self.add_class("error")

    def _format_result(self) -> str:
        """Format tool result for display."""
        if self._is_error:
            label = f"Error: {self._tool_name}"
        else:
            label = f"Result: {self._tool_name}"
        lines = [label]

        # Handle both string results and objects with .content attribute
        max_len = ToolResultEvent.MAX_RESULT_DISPLAY
        if isinstance(self._result, str):
            content = self._result
            if len(content) > max_len:
                content = content[:max_len] + _TRUNCATION_INDICATOR
            lines.append(content)
        elif hasattr(self._result, "content"):
            content = self._result.content
            if isinstance(content, str):
                # Truncate long results
                if len(content) > max_len:
                    content = content[:max_len] + _TRUNCATION_INDICATOR
                lines.append(content)
            else:
                content_str = json.dumps(content, indent=2, default=str)
                lines.append(_truncate_text(content_str, max_len))

        return "\n".join(lines)


class StatusMessage(BaseMessage):
    """Widget for displaying status updates."""

    DEFAULT_CSS = """
    StatusMessage {
        color: $text-muted;
        padding: 0 1;
        margin: 0;
        background: transparent;
        border: none;
    }
    """


class TurnSeparator(BaseMessage):
    """Widget for visually separating conversation turns."""

    DEFAULT_CSS = """
    TurnSeparator {
        color: $text-muted;
        padding: 0 1;
        margin: 1 0;
        background: transparent;
        border: none;
    }
    """


class ErrorMessage(BaseMessage):
    """Widget for displaying errors."""

    DEFAULT_CSS = """
    ErrorMessage {
        background: $error-darken-3;
        border: solid $error;
    }
    """

    def __init__(self, message: str, error_type: str = "error", **kwargs: Any) -> None:
        self._message = message
        self._error_type = error_type
        content = self._format_error()
        super().__init__(content, **kwargs)

    def _format_error(self) -> str:
        """Format error for display."""
        return f"[bold red]ERROR {self._error_type}:[/bold red] {self._message}"


def _format_approval_request(
    request: ApprovalRequest,
    queue_index: int | None,
    queue_total: int | None,
) -> str:
    lines = []
    if queue_index is not None and queue_total is not None:
        lines.extend(
            [
                f"[bold red]Approval {queue_index} of {queue_total}[/bold red]",
                f"Tool: {request.tool_name}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"[bold red]Approval Required: {request.tool_name}[/bold red]",
                "",
            ]
        )

    if request.description:
        lines.append(f"Reason: {request.description}")
        lines.append("")

    if request.tool_args:
        args_str = json.dumps(request.tool_args, indent=2, default=str)
        lines.append(f"Arguments:\n{args_str}")
        lines.append("")

    lines.extend(
        [
            "[green][[a]][/green] Approve once",
            "[green][[s]][/green] Approve for session",
            "[red][[d]][/red] Deny",
            "[red][[q]][/red] Quit",
        ]
    )

    return "\n".join(lines)


class ApprovalPanel(Static):
    """Pinned approval panel above the input box."""

    DEFAULT_CSS = """
    ApprovalPanel {
        background: $error-darken-3;
        border: solid $error;
        padding: 1;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self.styles.display = "none"

    def show_request(
        self,
        request: ApprovalRequest,
        queue_index: int | None = None,
        queue_total: int | None = None,
    ) -> None:
        self.update(_format_approval_request(request, queue_index, queue_total))
        self.styles.display = "block"

    def clear_request(self) -> None:
        self.update("")
        self.styles.display = "none"


class MessageContainer(ScrollableContainer):
    """Scrollable container for all messages.

    Handles streaming text responses and routing events to widgets.
    """

    DEFAULT_CSS = """
    MessageContainer {
        height: 100%;
        padding: 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._current_assistant: AssistantMessage | None = None

    def start_assistant_message(self, content: str = "") -> AssistantMessage:
        """Start a new assistant message for streaming."""
        self._current_assistant = AssistantMessage(content)
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

    def add_user_message(self, content: str) -> UserMessage:
        """Add a user message."""
        self._current_assistant = None
        msg = UserMessage(content)
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def add_status(self, text: str) -> StatusMessage:
        """Add a status message."""
        msg = StatusMessage(f"[dim]{text}[/dim]")
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def add_turn_separator(self) -> TurnSeparator:
        """Add a visual separator between turns."""
        msg = TurnSeparator("─" * 48)
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def add_error(self, message: str, error_type: str = "error") -> ErrorMessage:
        """Add an error message."""
        self._current_assistant = None  # End any streaming
        msg = ErrorMessage(message, error_type)
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def handle_event(self, event: "UIEvent") -> None:
        """Route events to the right widget/streaming handler.

        This method handles the TextResponseEvent streaming specially,
        and delegates other events to create_widget().
        """
        from llm_do.ui.events import (
            ApprovalRequestEvent,
            ErrorEvent,
            TextResponseEvent,
            ToolCallEvent,
            ToolResultEvent,
            UserMessageEvent,
        )

        # Handle TextResponseEvent specially for streaming
        if isinstance(event, TextResponseEvent):
            if event.is_delta:
                self.append_to_assistant(event.content)
            elif event.is_complete:
                self.finalize_assistant(event.content)
            else:
                # Start of streaming (is_complete=False, is_delta=False)
                placeholder = event.content or "Generating response..."
                self.start_assistant_message(placeholder)
            return

        # Interrupt streaming for tool/approval/error events
        if isinstance(
            event,
            (ToolCallEvent, ToolResultEvent, ApprovalRequestEvent, ErrorEvent, UserMessageEvent),
        ):
            self._current_assistant = None

        # Delegate to event's create_widget()
        widget = event.create_widget()
        if widget is not None:
            self.mount(widget)
            self.scroll_end(animate=False)
