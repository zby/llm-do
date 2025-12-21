# Textual UI Integration

## Prerequisites
- [x] 10-async-cli-adoption complete (async event loop in production)

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
- [x] Add `textual>=1.0.0` to dependencies
- [ ] Add `textual-speedups>=0.2.1` for performance (deferred - optional optimization)
- [x] Verify compatibility with existing Rich usage

### Phase 2: Basic App Shell
Create `llm_do/ui/app.py`:
- [x] `LlmDoApp(App)` - Main Textual application class
- [x] Basic screen layout: scrollable content area + input area
- [x] Wire to async CLI as default interactive output

### Phase 2b: Headless/Non-TTY Support
Ensure the CLI works in non-interactive environments (CI/CD, cron, pipes, containers):
- [x] Auto-detect when stdin/stdout is not a TTY (`sys.stdout.isatty()`)
- [x] Fall back to headless output when no TTY
- [x] Add `--headless` flag to force non-interactive mode regardless of TTY detection
- [x] Ensure approval flow behaves in headless mode (stdin prompts when TTY, otherwise `--approve-all` or `--strict`)
- [x] Document behavior matrix: `--headless` vs `--json` vs auto-detect (in Design Decisions)

### Phase 3: Message Display
Create `llm_do/ui/widgets/messages.py`:
- [x] `MessageContainer` - Scrollable message history
- [x] `BaseMessage` - Base widget for all message types
- [ ] `UserMessage` - Display user input (deferred to Phase 5)
- [x] `AssistantMessage` - Display model response (with streaming support)
- [x] `StatusMessage` - Display status updates
- [x] `ToolCallMessage` - Display tool calls
- [x] `ToolResultMessage` - Display tool results
- [x] `ApprovalMessage` - Display approval requests

### Phase 4: Event Integration
Event handling integrated directly in `llm_do/ui/app.py`:
- [x] Map `message_callback` events to widget creation
- [x] Handle streaming text (append to existing widget)
- [x] Integrate with existing `DisplayBackend` abstraction via `TextualDisplayBackend`

### Phase 5: Input Handling
- [x] Basic text input widget (disabled for now - single-shot mode)
- [ ] Handle Enter to submit
- [x] Handle Ctrl+C for interrupt
- [ ] Command history (up/down arrows)

### Phase 6: Approval Flow (Basic)
- [x] Display approval request as a message/panel
- [x] Accept keyboard input for approval (a/s/d/q)
- [x] Wire async approval callback to Textual event loop

## Current State
**Complete.** TUI is now the default interactive mode:
- `llm_do/ui/app.py` - Main Textual app with event consumption
- `llm_do/ui/widgets/messages.py` - Message display widgets
- `llm_do/ui/display.py` - Textual, Rich, Headless, and JSON display backends
- `llm_do/cli_async.py` - TUI default, `--headless` and `--json` for non-interactive modes

**Remaining work (optional/future):**
- Phase 5 input handling (Enter to submit, command history) - for multi-turn conversations
- Optional: `textual-speedups` for performance

## Design Decisions

### TUI is the default
The Textual TUI is the default interactive mode when stdout is a TTY.

### DisplayBackend abstraction
The TUI integrates with the existing `DisplayBackend` abstraction:
```
DisplayBackend (ABC)
├── TextualDisplayBackend ← default (interactive)
├── RichDisplayBackend    ← buffered log output / headless rich
├── HeadlessDisplayBackend← plain text output
└── JsonDisplayBackend    ← for --json mode
```

### Output mode hierarchy
1. `--json` → JsonDisplayBackend, no interactivity
2. `--headless` → headless output, no interactivity (prompts on stdin if TTY)
3. Auto-detect: TTY present → TextualDisplayBackend (default), no TTY → headless output

## Notes
- Keep it simple - this is foundation work
- Don't over-engineer widgets yet - Task 03 will refine based on Vibe patterns
- Ensure `--json` mode still works (bypasses TUI entirely)

## References
- Textual docs: https://textual.textualize.io/
- Textual widgets: https://textual.textualize.io/widget_gallery/
- UI architecture: `docs/ui.md`
- Async CLI: `llm_do/cli_async.py`
- Display backends: `llm_do/ui/display.py`
