"""Textual TUI application for llm-do.

The TUI app is a thin consumer that just mounts widgets and manages approval state.
All event discrimination happens once, in the parser.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine

from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalRequest
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, TextArea

from .controllers import (
    ApprovalWorkflowController,
    ExitConfirmationController,
    ExitDecision,
    InputHistoryController,
    WorkerRunner,
)
from .events import (
    ApprovalRequestEvent,
    CompletionEvent,
    ErrorEvent,
    TextResponseEvent,
    UIEvent,
)
from .widgets.messages import ApprovalPanel, MessageContainer


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

    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+j", "submit_message", "Send", show=True, key_display="Ctrl+J"),
        Binding("ctrl+m", "submit_message", "Send", show=False),
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
        self._auto_quit = auto_quit
        self._runner = WorkerRunner(run_turn=run_turn)
        self._approvals = ApprovalWorkflowController()
        self._approval_panel: ApprovalPanel | None = None
        self._done = False
        self._messages: list[str] = []
        self._input_history = InputHistoryController()
        self._exit_confirmation = ExitConfirmationController()
        self.final_result: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield MessageContainer(id="messages")
        yield Vertical(
            ApprovalPanel(id="approval-panel"),
            TextArea(
                "",
                id="user-input",
                disabled=True,
                show_line_numbers=False,
                soft_wrap=True,
                tab_behavior="focus",
                placeholder="Enter for newline; Ctrl+J to send",
            ),
            id="input-container",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Start the event consumer and worker when app mounts."""
        self._event_task = asyncio.create_task(self._consume_events())
        if self._worker_coro is not None:
            self._runner.start_background(self._worker_coro)
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

            if isinstance(event, ApprovalRequestEvent):
                self._enqueue_approval_request(event, messages)
            else:
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
        - ApprovalRequestEvent: handled separately to support queued approvals
        """
        if isinstance(event, TextResponseEvent):
            if event.is_complete:
                # Capture complete response for final output
                self._messages.append(event.content)
        elif isinstance(event, CompletionEvent):
            if not self._auto_quit:
                if not self._has_pending_approvals():
                    user_input = self.query_one("#user-input", TextArea)
                    user_input.disabled = False
                    user_input.focus()
        elif isinstance(event, ErrorEvent):
            if self._auto_quit:
                self._done = True
                self.exit()

    def _has_pending_approvals(self) -> bool:
        return self._approvals.has_pending()

    def _enqueue_approval_request(
        self,
        event: ApprovalRequestEvent,
        messages: MessageContainer,
    ) -> None:
        request = event.request or ApprovalRequest(
            tool_name=event.tool_name,
            tool_args=event.args,
            description=event.reason,
        )

        # TODO: Sequential approval queue UX may change as we refine stacking behavior.
        self._approvals.enqueue(request)
        self._render_active_approval()

        user_input = self.query_one("#user-input", TextArea)
        user_input.disabled = True
        messages.focus()

    def _render_active_approval(self) -> None:
        pending = self._approvals.current()
        if pending is None:
            return
        if self._approval_panel is None:
            self._approval_panel = self.query_one("#approval-panel", ApprovalPanel)
        self._approval_panel.show_request(
            pending.request,
            pending.queue_index,
            pending.queue_total,
        )

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
        self._resolve_approval(ApprovalDecision(approved=True))

    def action_approve_session(self) -> None:
        """Handle 's' key - approve for session."""
        self._resolve_approval(ApprovalDecision(approved=True, remember="session"))

    def action_deny(self) -> None:
        """Handle 'd' key - deny."""
        self._resolve_approval(ApprovalDecision(approved=False, note="Rejected via TUI"))

    def _resolve_approval(self, decision: ApprovalDecision) -> None:
        if not self._approvals.has_pending() or not self._approval_response_queue:
            return
        self._approval_response_queue.put_nowait(decision)
        self._approvals.pop_current()

        if self._approvals.has_pending():
            self._render_active_approval()
            return

        if self._approval_panel is None:
            self._approval_panel = self.query_one("#approval-panel", ApprovalPanel)
        self._approval_panel.clear_request()
        user_input = self.query_one("#user-input", TextArea)
        user_input.disabled = False
        user_input.focus()

    async def action_quit(self) -> None:
        """Quit the app."""
        self._done = True
        self.exit()

    async def action_quit_if_idle(self) -> None:
        """Quit the app if the input isn't active.

        Note: check_action() already prevents this from being called when input is active.
        """
        decision = self._exit_confirmation.request()
        if decision == ExitDecision.PROMPT:
            messages = self.query_one("#messages", MessageContainer)
            messages.add_status("Press 'q' again to exit.")
            return
        await self.action_quit()

    def action_submit_message(self) -> None:
        """Submit the current input if it is active."""
        if self._input_is_active():
            self._submit_current_input()

    def set_message_history(self, history: list[Any] | None) -> None:
        self._runner.set_message_history(history)

    def on_key(self, event: events.Key) -> None:
        """Handle key events for submission and history."""
        if not self._input_is_active():
            return
        if event.key in {"ctrl+j", "ctrl+m"}:
            event.prevent_default().stop()
            self._submit_current_input()
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
        if self._runner.is_running():
            messages = self.query_one("#messages", MessageContainer)
            messages.add_status("Wait for the current response to finish.")
            return
        user_input = self.query_one("#user-input", TextArea)
        user_text = user_input.text.strip()
        if not user_text:
            return
        user_input.text = ""
        self._exit_confirmation.reset()
        self._input_history.record_submission(user_text)
        asyncio.create_task(self._submit_user_message(user_text))

    async def _submit_user_message(self, text: str) -> None:
        """Submit a new user message and run another turn."""
        user_input = self.query_one("#user-input", TextArea)
        if self._runner.message_history:
            messages = self.query_one("#messages", MessageContainer)
            messages.add_turn_separator()

        if self._runner.run_turn is None:
            messages = self.query_one("#messages", MessageContainer)
            messages.add_status("Conversation runner not configured.")
            user_input.focus()
            return

        user_input.disabled = True

        task = self._runner.start_turn_task(text)

        def _on_done(done_task: asyncio.Task[list[Any] | None]) -> None:
            try:
                done_task.result()
            except Exception as e:
                try:
                    messages = self.query_one("#messages", MessageContainer)
                    messages.add_status(f"Conversation runner error: {e}")
                except Exception:
                    pass
            finally:
                user_input.disabled = False
                user_input.focus()

        task.add_done_callback(_on_done)

    def _history_previous(self) -> bool:
        """Move to the previous history entry if possible."""
        user_input = self.query_one("#user-input", TextArea)
        if not self._input_history.entries or not user_input.cursor_at_first_line:
            return False
        nav = self._input_history.previous(user_input.text)
        if not nav.handled:
            return False
        if nav.text is not None:
            user_input.text = nav.text
            user_input.move_cursor(user_input.document.end)
        return True

    def _history_next(self) -> bool:
        """Move to the next history entry if possible."""
        user_input = self.query_one("#user-input", TextArea)
        if not user_input.cursor_at_last_line:
            return False
        nav = self._input_history.next()
        if not nav.handled:
            return False
        if nav.text is not None:
            user_input.text = nav.text
            user_input.move_cursor(user_input.document.end)
        return True
