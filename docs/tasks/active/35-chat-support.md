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

## Tasks

### Phase 1: Input Enablement
- [ ] Enable input widget after worker response completes
- [ ] Handle Enter to submit new message
- [ ] Handle Ctrl+C to cancel/exit

### Phase 2: Conversation Loop
- [ ] Pass conversation history to subsequent `agent.run()` calls
- [ ] Maintain message history in TUI state
- [ ] Display user messages in conversation flow (`UserMessage` widget)

### Phase 3: History & UX
- [ ] Command history (up/down arrows for previous inputs)
- [ ] Multi-line input support (Shift+Enter or similar)
- [ ] Clear visual separation between turns

## Current State
Not started. Phase 5 of Task 20 laid groundwork (input widget exists but disabled).

## Notes
- pydantic-ai agents support conversation history via `message_history` parameter
- Keep approval flow working (approvals can happen mid-conversation)
- Consider: should `/exit` be a slash command or just Ctrl+C?

## References
- Task 20 Phase 5: Input handling (deferred items)
- pydantic-ai conversation history: agent.run(..., message_history=...)
