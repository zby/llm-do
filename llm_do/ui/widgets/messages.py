"""Message display widgets for the Textual TUI."""
from __future__ import annotations

import json
from typing import Any

from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import Static

from pydantic_ai_blocking_approval import ApprovalRequest


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
        super().__init__(content, **kwargs)
        self._content = content

    def append_text(self, text: str) -> None:
        """Append streaming text to this message."""
        self._content += text
        self.update(self._content)


class ToolCallMessage(BaseMessage):
    """Widget for displaying tool calls."""

    DEFAULT_CSS = """
    ToolCallMessage {
        background: $warning-darken-3;
        border: solid $warning;
    }
    """

    def __init__(self, tool_name: str, tool_call: Any, **kwargs: Any) -> None:
        self._tool_name = tool_name
        self._tool_call = tool_call

        # Format the tool call for display
        content = self._format_tool_call()
        super().__init__(content, **kwargs)

    def _format_tool_call(self) -> str:
        """Format tool call for display."""
        lines = [f"[bold yellow]Tool: {self._tool_name}[/bold yellow]"]

        if hasattr(self._tool_call, "args"):
            args = self._tool_call.args
            if isinstance(args, dict):
                args_str = json.dumps(args, indent=2)
            else:
                args_str = str(args)
            lines.append(f"Args: {args_str}")

        return "\n".join(lines)


class ToolResultMessage(BaseMessage):
    """Widget for displaying tool results."""

    DEFAULT_CSS = """
    ToolResultMessage {
        background: $success-darken-3;
        border: solid $success;
    }
    """

    def __init__(self, tool_name: str, result: Any, **kwargs: Any) -> None:
        self._tool_name = tool_name
        self._result = result

        content = self._format_result()
        super().__init__(content, **kwargs)

    def _format_result(self) -> str:
        """Format tool result for display."""
        lines = [f"[bold green]Result: {self._tool_name}[/bold green]"]

        if hasattr(self._result, "content"):
            content = self._result.content
            if isinstance(content, str):
                # Truncate long results
                if len(content) > 500:
                    content = content[:500] + "..."
                lines.append(content)
            else:
                lines.append(json.dumps(content, indent=2, default=str)[:500])

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


class ApprovalMessage(BaseMessage):
    """Widget for displaying approval requests."""

    DEFAULT_CSS = """
    ApprovalMessage {
        background: $error-darken-3;
        border: solid $error;
    }

    ApprovalMessage .title {
        text-style: bold;
        color: $error;
    }

    ApprovalMessage .options {
        margin-top: 1;
    }
    """

    def __init__(self, request: ApprovalRequest, **kwargs: Any) -> None:
        self._request = request
        content = self._format_request()
        super().__init__(content, **kwargs)

    def _format_request(self) -> str:
        """Format approval request for display."""
        lines = [
            f"[bold red]Approval Required: {self._request.tool_name}[/bold red]",
            "",
        ]

        if self._request.description:
            lines.append(f"Reason: {self._request.description}")
            lines.append("")

        if self._request.tool_args:
            args_str = json.dumps(self._request.tool_args, indent=2, default=str)
            lines.append(f"Arguments:\n{args_str}")
            lines.append("")

        lines.extend([
            "[green][a][/green] Approve once",
            "[green][s][/green] Approve for session",
            "[red][d][/red] Deny",
            "[red][q][/red] Quit",
        ])

        return "\n".join(lines)


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

    def add_tool_call(self, tool_name: str, tool_call: Any) -> ToolCallMessage:
        """Add a tool call message."""
        self._current_assistant = None  # End any streaming
        msg = ToolCallMessage(tool_name, tool_call)
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def add_tool_result(self, tool_name: str, result: Any) -> ToolResultMessage:
        """Add a tool result message."""
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
        self._current_assistant = None
        msg = ApprovalMessage(request)
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg
