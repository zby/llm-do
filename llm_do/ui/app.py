"""Textual TUI application for llm-do."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.widgets import Footer, Header, Input, Static

from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalRequest

from .widgets.messages import (
    ApprovalMessage,
    AssistantMessage,
    MessageContainer,
    StatusMessage,
    ToolCallMessage,
    ToolResultMessage,
)


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

    .assistant-message {
        background: $primary-background;
        padding: 1;
        margin: 1 0;
        border: solid $primary;
    }

    .tool-call-message {
        background: $warning-darken-3;
        padding: 1;
        margin: 1 0;
        border: solid $warning;
    }

    .tool-result-message {
        background: $success-darken-3;
        padding: 1;
        margin: 1 0;
        border: solid $success;
    }

    .status-message {
        color: $text-muted;
        padding: 0 1;
        margin: 0;
    }

    .approval-message {
        background: $error-darken-3;
        padding: 1;
        margin: 1 0;
        border: solid $error;
    }

    .approval-message .title {
        color: $error;
        text-style: bold;
    }

    .approval-message .options {
        margin-top: 1;
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
        event_queue: asyncio.Queue[Any],
        approval_response_queue: asyncio.Queue[ApprovalDecision] | None = None,
        worker_coro: Any | None = None,
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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield MessageContainer(id="messages")
        yield Vertical(
            Input(placeholder="Enter message...", id="user-input", disabled=True),
            id="input-container",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Start the event consumer and worker when app mounts."""
        self._event_task = asyncio.create_task(self._consume_events())
        if self._worker_coro is not None:
            self._worker_task = asyncio.create_task(self._worker_coro)

    async def on_unmount(self) -> None:
        """Clean up on unmount."""
        if hasattr(self, "_event_task"):
            self._event_task.cancel()

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
                # Capture final result for display after exit
                if self._messages:
                    self.final_result = "\n".join(self._messages)
                if self._auto_quit:
                    self.exit()
                else:
                    messages.add_status("Press 'q' to exit")
                break

            # Handle CLIEvent
            if hasattr(event, "kind") and hasattr(event, "payload"):
                if event.kind == "runtime_event":
                    self._handle_runtime_event(event.payload, messages)
                elif event.kind == "deferred_tool":
                    self._handle_deferred_tool(event.payload, messages)
                elif event.kind == "approval_request":
                    await self._handle_approval_request(event.payload, messages)

            self._event_queue.task_done()

    def _handle_runtime_event(self, payload: Any, messages: MessageContainer) -> None:
        """Handle a runtime event from the worker."""
        # Handle different pydantic-ai event types
        event_type = type(payload).__name__

        # Handle dict payloads (serialized events)
        if isinstance(payload, dict):
            self._handle_dict_event(payload, messages)
            return

        if event_type == "PartDeltaEvent":
            # Streaming text delta
            if hasattr(payload, "delta") and hasattr(payload.delta, "content_delta"):
                content = payload.delta.content_delta
                messages.append_to_assistant(content)
                # Capture for final output
                if self._messages:
                    self._messages[-1] += content
                else:
                    self._messages.append(content)
        elif event_type == "PartStartEvent":
            # New part starting
            if hasattr(payload, "part"):
                part_type = type(payload.part).__name__
                if part_type == "TextPart":
                    messages.start_assistant_message()
                    # Start new message capture
                    self._messages.append("")
                elif part_type == "ToolCallPart":
                    tool_name = getattr(payload.part, "tool_name", "tool")
                    messages.add_tool_call(tool_name, payload.part)
        elif event_type == "ToolReturnEvent":
            # Tool completed
            tool_name = getattr(payload, "tool_name", "tool")
            messages.add_tool_result(tool_name, payload)
        elif event_type == "FinalResultEvent":
            messages.add_status("Response complete")
        elif event_type == "str":
            # Error or status message passed as string
            messages.add_status(str(payload))
        else:
            # Generic fallback
            messages.add_status(f"Event: {event_type}")

    def _handle_dict_event(self, payload: dict[str, Any], messages: MessageContainer) -> None:
        """Handle dict-based event payloads from message callback."""
        from pydantic_ai.messages import (
            PartEndEvent,
            TextPart,
            FunctionToolCallEvent,
            FunctionToolResultEvent,
        )

        # Extract worker name and event from wrapper dict
        worker = payload.get("worker", "worker")

        # Handle initial_request preview
        if "initial_request" in payload:
            preview = payload.get("initial_request")
            if preview:
                messages.add_status(f"[{worker}] Starting...")
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
                        messages.add_status(f"[{worker}] {phase} {state} ({model})")
                    else:
                        messages.add_status(f"[{worker}] {phase} {state}")
                else:
                    messages.add_status(f"[{worker}] {status}")
            else:
                messages.add_status(f"[{worker}] {status}")
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
                if messages._current_assistant is None:
                    messages.start_assistant_message()
                messages.append_to_assistant(part.content)
                # Capture for final output
                self._messages.append(part.content)
        elif isinstance(event, FunctionToolCallEvent):
            # Tool call
            tool_name = getattr(event.part, "tool_name", "tool")
            messages.add_tool_call(tool_name, event.part)
        elif isinstance(event, FunctionToolResultEvent):
            # Tool result
            tool_name = getattr(event, "tool_name", "tool")
            messages.add_tool_result(tool_name, event.result)

    def _handle_deferred_tool(
        self, payload: dict[str, Any], messages: MessageContainer
    ) -> None:
        """Handle a deferred tool status update."""
        tool_name = payload.get("tool_name", "tool")
        status = payload.get("status", "pending")
        messages.add_status(f"Deferred tool '{tool_name}': {status}")

    async def _handle_approval_request(
        self,
        request: ApprovalRequest,
        messages: MessageContainer,
    ) -> None:
        """Display approval request and wait for user input."""
        self._pending_approval = request

        # Add approval message to the display
        messages.add_approval_request(request)

        # Update footer to show approval bindings
        self._update_approval_bindings(show=True)

    def _update_approval_bindings(self, show: bool) -> None:
        """Show or hide approval-related key bindings."""
        # Update bindings visibility
        for binding in self.BINDINGS:
            if binding.key in ("a", "s", "d", "q"):
                # Bindings are immutable, so we toggle via CSS or other means
                pass
        self.refresh_bindings()

    def action_approve(self) -> None:
        """Handle 'a' key - approve once."""
        if self._pending_approval and self._approval_response_queue:
            self._approval_response_queue.put_nowait(ApprovalDecision(approved=True))
            self._pending_approval = None
            self._update_approval_bindings(show=False)

    def action_approve_session(self) -> None:
        """Handle 's' key - approve for session."""
        if self._pending_approval and self._approval_response_queue:
            self._approval_response_queue.put_nowait(
                ApprovalDecision(approved=True, remember="session")
            )
            self._pending_approval = None
            self._update_approval_bindings(show=False)

    def action_deny(self) -> None:
        """Handle 'd' key - deny."""
        if self._pending_approval and self._approval_response_queue:
            self._approval_response_queue.put_nowait(
                ApprovalDecision(approved=False, note="Rejected via TUI")
            )
            self._pending_approval = None
            self._update_approval_bindings(show=False)

    def signal_done(self) -> None:
        """Signal that the worker is done."""
        self._done = True
