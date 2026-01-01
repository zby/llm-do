# Chat Support (Multi-turn Conversations)

## Prerequisites
- [x] 20-textual-ui-integration (TUI foundation with basic input widget)

## Goal
Enable multi-turn conversations in the TUI where users can send follow-up messages after the initial response.

## Background

Currently llm-do is single-shot: user provides prompt, worker responds, done. Multi-turn chat requires:
- Input handling after response completes
- Conversation history management
- UI for displaying the back-and-forth

This is foundational for slash commands (Task 40) which need input parsing during conversations.

### Vibe Compatibility

This implementation is designed to align with Task 30 (Vibe UI Patterns):
- Widget hierarchy matches Vibe's structure (`UserMessage` in `MessageContainer`)
- Input handling is extensible for later additions (slash commands, autocomplete)
- Event pattern (`UserMessageEvent`) follows existing typed event system
- Conversation loop pattern mirrors Vibe's `_handle_agent_turn()`

## Tasks

### Phase 1: Runtime Support for Message History
Add `message_history` parameter to the execution stack (new architecture).

- [x] `llm_do/ctx_runtime/invocables.py`: Pass `message_history` to `agent.run()` / `agent.run_stream()`
- [x] `llm_do/ctx_runtime/ctx.py`: Store and propagate `message_history` on `Context`
- [x] `llm_do/ctx_runtime/cli.py`: Plumb `message_history` into `run()` / TUI turn runner

```python
# In invocables.py WorkerInvocable._run_with_event_stream():
result = await agent.run(
    prompt,
    deps=ctx,
    model_settings=self.model_settings,
    event_stream_handler=event_stream_handler,
    message_history=ctx.messages or None,  # NEW
)
ctx.messages = list(result.all_messages())
```

### Phase 2: UserMessage Widget & Event
Add UI components for displaying user input in the conversation (new architecture).

- [x] `llm_do/ui/events.py`: Add `UserMessageEvent` class
- [x] `llm_do/ui/widgets/messages.py`: Add `UserMessage` widget
- [x] `llm_do/ui/widgets/messages.py`: Add `add_user_message()` to `MessageContainer`

```python
# UserMessage widget (matches Vibe hierarchy)
class UserMessage(BaseMessage):
    """Widget for displaying user input."""
    DEFAULT_CSS = """
    UserMessage {
        background: $surface;
        border: solid $secondary;
    }
    """
```

### Phase 3: Input Enablement
Enable input widget after worker response completes (new architecture).

- [x] `llm_do/ui/app.py`: Enable input widget on CompletionEvent (non-auto-quit mode)
- [x] `llm_do/ui/app.py`: Handle `Input.Submitted` event
- [x] `llm_do/ui/app.py`: Rebind 'q' to only work when not in input mode

```python
# In LlmDoApp:
def on_input_submitted(self, event: Input.Submitted) -> None:
    """Handle Enter in input widget."""
    user_text = event.value.strip()
    if user_text:
        self._submit_user_message(user_text)
    event.input.clear()
```

### Phase 4: Conversation Loop
Implement the multi-turn conversation loop in the TUI (new architecture).

- [x] `llm_do/ui/app.py`: Track `_message_history` (list of pydantic-ai messages)
- [x] `llm_do/ui/app.py`: Add `_submit_user_message()` method
- [x] `llm_do/ui/app.py`: Create new worker task for each turn
- [x] `llm_do/ctx_runtime/cli.py`: Wire `run_turn` into the TUI and keep the app alive

```python
# Conversation loop in LlmDoApp:
async def _submit_user_message(self, text: str) -> None:
    """Submit a new user message and run another turn."""
    # 1. Display user message
    messages = self.query_one("#messages", MessageContainer)
    messages.add_user_message(text)

    # 2. Disable input during processing
    self.query_one("#user-input", Input).disabled = True
    self._done = False

    # 3. Run next turn with history
    self._worker_task = asyncio.create_task(
        self._run_turn(text, self._message_history)
    )
```

### Phase 5: CLI Integration
Refactor CLI to support conversation mode (new architecture).

- [x] `llm_do/ctx_runtime/cli.py`: Extract worker execution into reusable function
- [x] `llm_do/ctx_runtime/cli.py`: Pass message history between turns
- [x] `llm_do/ctx_runtime/cli.py`: Capture returned messages for next turn

```python
# New pattern in ctx_runtime/cli.py:
async def run_single_turn(
    prompt: str,
    message_history: list[Any] | None = None,
) -> Any:
    """Run a single conversation turn."""
    _result, ctx = await run(
        ...,
        message_history=message_history,
    )
    return list(ctx.messages)  # updated history for next turn
```

### Phase 6: UX Polish (Optional for initial release)
- [x] Command history (up/down arrows for previous inputs)
- [x] Multi-line input support (Shift+Enter or similar)
- [x] Clear visual separation between turns
- [x] Exit confirmation or `/exit` command

## Implementation Details

### File Changes Summary

| File | Changes |
|------|---------|
| `llm_do/ctx_runtime/invocables.py` | Pass `message_history` to `agent.run()` / `agent.run_stream()` and update stored messages |
| `llm_do/ctx_runtime/ctx.py` | Store and propagate `message_history` on `Context` |
| `llm_do/ctx_runtime/cli.py` | Wire conversation turns and history plumbing |
| `llm_do/ui/events.py` | Add `UserMessageEvent` class |
| `llm_do/ui/widgets/messages.py` | Add `UserMessage` widget, `add_user_message()` method |
| `llm_do/ui/app.py` | Conversation loop, input handling, history tracking |

### Message History Flow

```
Turn 1:
  CLI args → run(..., message_history=None)
           → agent.run() → result.all_messages()
           → TUI displays response
           → Store result.all_messages() as _message_history

Turn 2+:
  User input → _submit_user_message(text)
            → run_single_turn(text, _message_history)
            → agent.run(message_history=_message_history)
            → Replace _message_history with result.all_messages()
            → TUI displays response
```

### Key Design Decisions

1. **Input enabled after completion, not during streaming**
   - Simpler UX, avoids race conditions
   - Matches Vibe pattern

2. **History stored in TUI, not in worker**
   - Each turn is stateless from worker perspective
   - pydantic-ai handles history reconstruction

3. **Same worker definition for all turns**
   - No need to reload/recreate worker
   - Instructions persist across turns

4. **Approval flow unchanged**
   - Approvals can happen mid-conversation
   - Each turn respects same approval rules

## Current State
Phase 1, 4, 5, and 6 are now wired for the new architecture: message history is passed into `agent.run()` / `agent.run_stream()`, `Context` stores it, and the TUI uses a `run_turn` callback with `auto_quit=False` so follow-ups stay in the same session. Display backends are restored across TUI/headless/JSON, and the input supports history, multi-line entry, turn separators, and exit confirmation. Multi-turn chat is gated behind `--chat` in the CLI. Remaining work: none in this task.

## Notes
- pydantic-ai agents support conversation history via `message_history` parameter
- Use PydanticAI `ModelMessagesTypeAdapter` for history serialization when persistence is needed (binary parts stored as base64).
- For now, keep message history in-memory only; persistence can be added later.
- Replace history each turn with `result.all_messages()` (no delta tracking).
- Conversation mode only in TUI for now; headless remains single-shot.
- Sub-workers stay stateless: do not propagate conversation history to worker calls yet.
- Keep approval flow working (approvals can happen mid-conversation)
- Consider: should `/exit` be a slash command or just Ctrl+C? (deferred to Phase 6)
- Phase 6 items align with Task 30 Phase 5 (Enhanced Input)

## References
- Task 20 Phase 5: Input handling (deferred items)
- Task 30: Vibe UI Patterns (widget hierarchy, input handling)
- pydantic-ai conversation history: `agent.run(..., message_history=...)`
- Vibe's `_handle_agent_turn()` pattern: `vibe/cli/textual_ui/app.py`
