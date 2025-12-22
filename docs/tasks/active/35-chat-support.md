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
Add `message_history` parameter to the execution stack.

- [x] `llm_do/execution.py`: Pass `message_history` to `agent.run()`
- [x] `llm_do/runtime.py`: Add `message_history` param to `run_worker_async`
- [x] `llm_do/runtime.py`: Add `message_history` param to `run_tool_async`

```python
# In execution.py default_agent_runner_async():
run_result = await agent.run(
    exec_ctx.prompt,
    deps=context,
    event_stream_handler=exec_ctx.event_handler,
    message_history=message_history,  # NEW
)
```

### Phase 2: UserMessage Widget & Event
Add UI components for displaying user input in the conversation.

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
Enable input widget after worker response completes.

- [x] `llm_do/ui/app.py`: Enable input widget when `_done` is True
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
Implement the multi-turn conversation loop in the TUI.

- [x] `llm_do/ui/app.py`: Track `_message_history` (list of pydantic-ai messages)
- [x] `llm_do/ui/app.py`: Add `_submit_user_message()` method
- [x] `llm_do/ui/app.py`: Create new worker task for each turn
- [ ] `llm_do/cli_async.py`: Refactor to support conversation mode

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
Refactor CLI to support conversation mode.

- [x] `llm_do/cli_async.py`: Extract worker execution into reusable function
- [x] `llm_do/cli_async.py`: Pass message history between turns
- [x] `llm_do/cli_async.py`: Capture returned messages for next turn

```python
# New pattern in cli_async.py:
async def run_single_turn(
    prompt: str,
    message_history: list[Any] | None = None,
) -> WorkerRunResult:
    """Run a single conversation turn."""
    result = await run_tool_async(
        ...,
        message_history=message_history,
    )
    return result  # result.messages used for next turn
```

### Phase 6: UX Polish (Optional for initial release)
- [ ] Command history (up/down arrows for previous inputs)
- [ ] Multi-line input support (Shift+Enter or similar)
- [ ] Clear visual separation between turns
- [ ] Exit confirmation or `/exit` command

## Implementation Details

### File Changes Summary

| File | Changes |
|------|---------|
| `llm_do/execution.py` | Add `message_history` param to `default_agent_runner_async`, pass to `agent.run()` |
| `llm_do/runtime.py` | Add `message_history` param to `run_worker_async` and `run_tool_async` |
| `llm_do/ui/events.py` | Add `UserMessageEvent` class |
| `llm_do/ui/widgets/messages.py` | Add `UserMessage` widget, `add_user_message()` method |
| `llm_do/ui/app.py` | Conversation loop, input handling, history tracking |
| `llm_do/cli_async.py` | Refactor `run_worker_in_background` to support turns |

### Message History Flow

```
Turn 1:
  CLI args → run_tool_async(message_history=None)
           → agent.run() → result.messages
           → TUI displays response
           → Store result.messages as _message_history

Turn 2+:
  User input → _submit_user_message(text)
            → run_single_turn(text, _message_history)
            → agent.run(message_history=_message_history)
            → Append new messages to _message_history
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
Phase 1-5 complete: runtime/execution accept `message_history`, plus user-message UI support, input enablement, conversation-loop scaffolding, and CLI wiring for multi-turn runs. Phase 5 of Task 20 laid groundwork (input widget exists but disabled). Decisions: TUI-only conversation mode, in-memory history, replace history each turn with `run_result.all_messages`, and no sub-worker history propagation for now.

## Notes
- pydantic-ai agents support conversation history via `message_history` parameter
- Use PydanticAI `ModelMessagesTypeAdapter` for history serialization when persistence is needed (binary parts stored as base64).
- For now, keep message history in-memory only; persistence can be added later.
- Replace history each turn with `run_result.all_messages` (no delta tracking).
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
