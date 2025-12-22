"""Textual TUI application for llm-do.

The TUI app is a thin consumer that just mounts widgets and manages approval state.
All event discrimination happens once, in the parser.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input

from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalRequest

from .events import ApprovalRequestEvent, CompletionEvent, ErrorEvent, TextResponseEvent, UIEvent
from .widgets.messages import MessageContainer


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
        event_queue: asyncio.Queue[UIEvent | None],
        approval_response_queue: asyncio.Queue[ApprovalDecision] | None = None,
        worker_coro: Coroutine[Any, Any, Any] | None = None,
        run_turn: Callable[[str, list[Any] | None], Coroutine[Any, Any, Any]] | None = None,
        auto_quit: bool = True,
    ):
        super().__init__()
        self._event_queue = event_queue
        self._approval_response_queue = approval_response_queue
        self._worker_coro = worker_coro
        self._run_turn = run_turn
        self._auto_quit = auto_quit
        self._pending_approval: ApprovalRequest | None = None
        self._worker_task: asyncio.Task[Any] | None = None
        self._done = False
        self._messages: list[str] = []
        self._message_history: list[Any] = []
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
        """Consume typed events from the queue and update UI.

        This is a thin loop that delegates to MessageContainer for rendering
        and only handles app-level state management.
        """
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
        """Handle events that need app state management.

        Only handles:
        - TextResponseEvent: Capture complete responses for final output
        - ApprovalRequestEvent: Store pending approval for action handlers
        """
        if isinstance(event, TextResponseEvent):
            if event.is_complete:
                # Capture complete response for final output
                self._messages.append(event.content)
        elif isinstance(event, CompletionEvent):
            if self._auto_quit:
                if self._messages:
                    self.final_result = "\n".join(self._messages)
                self._done = True
                self.exit()
            else:
                user_input = self.query_one("#user-input", Input)
                user_input.disabled = False
                user_input.focus()
        elif isinstance(event, ErrorEvent):
            if self._auto_quit:
                self._done = True
                self.exit()
        elif isinstance(event, ApprovalRequestEvent):
            # Store pending approval for action handlers
            self._pending_approval = event.request

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

    def action_quit(self) -> None:
        """Quit the app unless the input widget has focus."""
        user_input = self.query_one("#user-input", Input)
        if user_input.has_focus:
            return
        self._done = True
        self.exit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter in the input widget."""
        user_text = event.value.strip()
        if not user_text:
            return
        event.input.clear()
        asyncio.create_task(self._submit_user_message(user_text))

    async def _submit_user_message(self, text: str) -> None:
        """Submit a new user message and run another turn."""
        messages = self.query_one("#messages", MessageContainer)
        messages.add_user_message(text)

        user_input = self.query_one("#user-input", Input)
        user_input.disabled = True

        if self._run_turn is None:
            messages.add_status("Conversation runner not configured.")
            user_input.disabled = False
            user_input.focus()
            return

        async def _run_turn_task() -> None:
            try:
                history = self._message_history or None
                result = await self._run_turn(text, history)
                if result is not None:
                    self._message_history = list(result.messages or [])
            finally:
                user_input.disabled = False
                user_input.focus()

        self._worker_task = asyncio.create_task(_run_turn_task())

    def signal_done(self) -> None:
        """Signal that the worker is done."""
        self._done = True
