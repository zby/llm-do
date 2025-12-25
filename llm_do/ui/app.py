"""Textual TUI application for llm-do.

The TUI app is a thin consumer that just mounts widgets and manages approval state.
All event discrimination happens once, in the parser.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Coroutine

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, TextArea

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
        min-height: 3;
        padding: 1;
        background: $surface;
    }

    #user-input {
        width: 100%;
        min-height: 4;
        max-height: 8;
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
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("q", "quit_if_idle", "Quit", show=False),
        Binding("a", "approve", "Approve", show=False),
        Binding("s", "approve_session", "Approve Session", show=False),
        Binding("d", "deny", "Deny", show=False),
    ]

    def __init__(
        self,
        event_queue: asyncio.Queue[UIEvent | None],
        approval_response_queue: asyncio.Queue[ApprovalDecision] | None = None,
        worker_coro: Coroutine[Any, Any, Any] | None = None,
        run_turn: Callable[
            [str, list[Any] | None],
            Coroutine[Any, Any, list[Any] | None],
        ] | None = None,
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
        self._input_history: list[str] = []
        self._input_history_index: int | None = None
        self._input_history_draft: str = ""
        self._exit_requested_at: float | None = None
        self.final_result: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield MessageContainer(id="messages")
        yield Vertical(
            TextArea(
                "",
                id="user-input",
                disabled=True,
                show_line_numbers=False,
                soft_wrap=True,
                tab_behavior="focus",
                placeholder="Enter message...",
            ),
            id="input-container",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Start the event consumer and worker when app mounts."""
        self._event_task = asyncio.create_task(self._consume_events())
        if self._worker_coro is not None:
            self._worker_task = asyncio.create_task(self._worker_coro)
        if not self._auto_quit:
            user_input = self.query_one("#user-input", TextArea)
            user_input.disabled = False
            user_input.focus()

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
            if not self._auto_quit:
                user_input = self.query_one("#user-input", TextArea)
                user_input.disabled = False
                user_input.focus()
        elif isinstance(event, ErrorEvent):
            if self._auto_quit:
                self._done = True
                self.exit()
        elif isinstance(event, ApprovalRequestEvent):
            # Store pending approval for action handlers
            self._pending_approval = event.request
            user_input = self.query_one("#user-input", TextArea)
            user_input.disabled = True
            messages = self.query_one("#messages", MessageContainer)
            messages.focus()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Disable quit binding while the input widget is active."""
        if action == "quit_if_idle":
            return not self._input_is_active()
        return super().check_action(action, parameters)

    def _input_is_active(self) -> bool:
        """Return True when the input widget is focused and editable."""
        try:
            user_input = self.query_one("#user-input", TextArea)
        except Exception:
            return False
        return user_input.has_focus and not user_input.disabled

    def action_approve(self) -> None:
        """Handle 'a' key - approve once."""
        if self._pending_approval and self._approval_response_queue:
            self._approval_response_queue.put_nowait(ApprovalDecision(approved=True))
            self._pending_approval = None
            user_input = self.query_one("#user-input", TextArea)
            user_input.disabled = False
            user_input.focus()

    def action_approve_session(self) -> None:
        """Handle 's' key - approve for session."""
        if self._pending_approval and self._approval_response_queue:
            self._approval_response_queue.put_nowait(
                ApprovalDecision(approved=True, remember="session")
            )
            self._pending_approval = None
            user_input = self.query_one("#user-input", TextArea)
            user_input.disabled = False
            user_input.focus()

    def action_deny(self) -> None:
        """Handle 'd' key - deny."""
        if self._pending_approval and self._approval_response_queue:
            self._approval_response_queue.put_nowait(
                ApprovalDecision(approved=False, note="Rejected via TUI")
            )
            self._pending_approval = None
            user_input = self.query_one("#user-input", TextArea)
            user_input.disabled = False
            user_input.focus()

    def action_quit(self) -> None:
        """Quit the app."""
        self._done = True
        self.exit()

    def action_quit_if_idle(self) -> None:
        """Quit the app if the input isn't active."""
        if not self._input_is_active():
            now = time.monotonic()
            if self._exit_requested_at is None or now - self._exit_requested_at > 2:
                self._exit_requested_at = now
                messages = self.query_one("#messages", MessageContainer)
                messages.add_status("Press 'q' again to exit.")
                return
            self.action_quit()

    def on_key(self, event: events.Key) -> None:
        """Handle key events for submission and history."""
        if not self._input_is_active():
            return
        if event.key == "enter":
            event.prevent_default().stop()
            self._submit_current_input()
            return
        if event.key == "shift+enter":
            event.prevent_default().stop()
            user_input = self.query_one("#user-input", TextArea)
            user_input.insert("\n")
            return
        if event.key == "up":
            if self._history_previous():
                event.prevent_default().stop()
            return
        if event.key == "down":
            if self._history_next():
                event.prevent_default().stop()
            return

    def _submit_current_input(self) -> None:
        """Submit the current text area content as a message."""
        if self._worker_task is not None and not self._worker_task.done():
            messages = self.query_one("#messages", MessageContainer)
            messages.add_status("Wait for the current response to finish.")
            return
        user_input = self.query_one("#user-input", TextArea)
        user_text = user_input.text.strip()
        if not user_text:
            return
        user_input.text = ""
        self._exit_requested_at = None
        self._input_history.append(user_text)
        self._input_history_index = None
        self._input_history_draft = ""
        asyncio.create_task(self._submit_user_message(user_text))

    async def _submit_user_message(self, text: str) -> None:
        """Submit a new user message and run another turn."""
        user_input = self.query_one("#user-input", TextArea)
        if self._message_history:
            messages = self.query_one("#messages", MessageContainer)
            messages.add_turn_separator()

        if self._run_turn is None:
            messages = self.query_one("#messages", MessageContainer)
            messages.add_status("Conversation runner not configured.")
            user_input.focus()
            return

        user_input.disabled = True

        async def _run_turn_task() -> None:
            try:
                history = self._message_history or None
                new_history = await self._run_turn(text, history)
                if new_history is not None:
                    self._message_history = list(new_history)
            finally:
                user_input.disabled = False
                user_input.focus()

        self._worker_task = asyncio.create_task(_run_turn_task())

    def signal_done(self) -> None:
        """Signal that the worker is done."""
        self._done = True

    def _history_previous(self) -> bool:
        """Move to the previous history entry if possible."""
        user_input = self.query_one("#user-input", TextArea)
        if not self._input_history or not user_input.cursor_at_first_line:
            return False
        if self._input_history_index is None:
            self._input_history_draft = user_input.text
            self._input_history_index = len(self._input_history) - 1
        elif self._input_history_index > 0:
            self._input_history_index -= 1
        else:
            return True
        user_input.text = self._input_history[self._input_history_index]
        user_input.move_cursor(user_input.document.end)
        return True

    def _history_next(self) -> bool:
        """Move to the next history entry if possible."""
        user_input = self.query_one("#user-input", TextArea)
        if self._input_history_index is None or not user_input.cursor_at_last_line:
            return False
        if self._input_history_index < len(self._input_history) - 1:
            self._input_history_index += 1
            user_input.text = self._input_history[self._input_history_index]
            user_input.move_cursor(user_input.document.end)
            return True
        user_input.text = self._input_history_draft
        user_input.move_cursor(user_input.document.end)
        self._input_history_index = None
        self._input_history_draft = ""
        return True
