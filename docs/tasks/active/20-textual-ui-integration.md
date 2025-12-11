# Textual UI Integration

## Prerequisites
- [ ] 10-async-cli-adoption complete (async event loop in production)

## Goal
Replace Rich panel output with interactive Textual TUI as a foundation for richer UI features.

## Background

Textual is a TUI framework from the same team as Rich. It provides:
- Reactive widgets with CSS-like styling
- Async-native event handling
- Composable layouts
- Works alongside Rich (same styling system)

This task establishes the Textual foundation. Specific UI patterns (borrowed from Mistral Vibe) come in Task 03.

## Tasks

### Phase 1: Dependencies
- [ ] Add `textual>=1.0.0` to dependencies
- [ ] Add `textual-speedups>=0.2.1` for performance
- [ ] Verify compatibility with existing Rich usage

### Phase 2: Basic App Shell
Create `llm_do/ui/app.py`:
- [ ] `LlmDoApp(App)` - Main Textual application class
- [ ] Basic screen layout: scrollable content area + input area
- [ ] Wire to async CLI as alternative to Rich output
- [ ] `--tui` flag to opt into Textual mode (Rich remains default initially)

### Phase 3: Message Display
Create `llm_do/ui/widgets/messages.py`:
- [ ] `MessageContainer` - Scrollable message history
- [ ] `BaseMessage` - Base widget for all message types
- [ ] `UserMessage` - Display user input
- [ ] `AssistantMessage` - Display model response (with streaming support)
- [ ] `StatusMessage` - Display status updates

### Phase 4: Event Integration
Create `llm_do/ui/event_handler.py`:
- [ ] Map `message_callback` events to widget creation
- [ ] Handle streaming text (append to existing widget)
- [ ] Integrate with existing `DisplayBackend` abstraction

### Phase 5: Input Handling
- [ ] Basic text input widget
- [ ] Handle Enter to submit
- [ ] Handle Ctrl+C for interrupt
- [ ] Command history (up/down arrows)

### Phase 6: Approval Flow (Basic)
- [ ] Display approval request as a message/panel
- [ ] Accept keyboard input for approval (a/s/d/q)
- [ ] Wire async approval callback to Textual event loop

## Current State
Not started. Waiting for 01-async-cli-adoption.

## Notes
- Keep it simple - this is foundation work
- Don't over-engineer widgets yet - Task 03 will refine based on Vibe patterns
- Ensure `--json` mode still works (bypasses TUI entirely)
- Consider: should TUI be opt-in (`--tui`) or opt-out (`--no-tui`)?

## References
- Textual docs: https://textual.textualize.io/
- Textual widgets: https://textual.textualize.io/widget_gallery/
- Our async experiment: `experiments/async_cli/`
