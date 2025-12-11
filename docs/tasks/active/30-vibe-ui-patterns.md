# Vibe UI Patterns Adoption

## Prerequisites
- [ ] 10-async-cli-adoption complete
- [ ] 20-textual-ui-integration complete (basic Textual app working)

## Goal
Adopt specific UI patterns from Mistral Vibe to create a polished, professional CLI experience while preserving llm-do's worker orchestration model.

## Background

Mistral Vibe (https://github.com/mistralai/mistral-vibe) has a well-designed Textual UI with:
- Sophisticated message widgets with tool call rendering
- Modal approval dialogs with keyboard navigation
- Streaming with content append
- Todo/task tracking display
- Status indicators and loading states

We borrow their **UI patterns**, not their agent architecture.

## What We Borrow vs Keep

### Borrow from Vibe
- Widget designs (message types, approval modal, status bar)
- Event handler dispatch pattern
- Streaming append pattern (`append_content()`)
- TCSS styling approach
- Keyboard shortcut patterns

### Keep from llm-do
- PydanticAI agent runner
- Worker composition (`worker_call`, `worker_create`)
- `pydantic-ai-blocking-approval` integration
- Config-driven toolset loading
- Per-worker sandbox/approval isolation

## Tasks

### Phase 1: Study Vibe Implementation
- [ ] Clone/review `vibe/cli/textual_ui/` structure
- [ ] Document widget hierarchy and responsibilities
- [ ] Identify reusable patterns vs Vibe-specific code
- [ ] Note any dependencies we'd need to add

### Phase 2: Enhanced Message Widgets
Upgrade `llm_do/ui/widgets/messages.py`:
- [ ] `ToolCallMessage` - Display tool invocations with syntax highlighting
- [ ] `ToolResultMessage` - Display tool results (collapsible for long output)
- [ ] `ErrorMessage` - Collapsible error display with traceback
- [ ] `WorkerDelegationMessage` - Show worker_call/worker_create (llm-do specific)
- [ ] Streaming support via `append_content()` method

### Phase 3: Modal Approval Dialog
Create `llm_do/ui/widgets/approval.py` (adapt Vibe's `ApprovalApp`):
- [ ] `ApprovalDialog` modal widget
- [ ] Options: Yes / Yes (always for session) / No
- [ ] Arrow key navigation + number shortcuts (1/2/3)
- [ ] Display tool name, args, description
- [ ] Optional feedback input on rejection
- [ ] Post messages: `ApprovalGranted`, `ApprovalRejected`

### Phase 4: Status & Loading
Create `llm_do/ui/widgets/status.py`:
- [ ] `LoadingIndicator` - Spinner/animation during model calls
- [ ] `StatusBar` - Bottom bar with mode, model, worker info
- [ ] `ModeIndicator` - Show current state (waiting, running, approval)

### Phase 5: Enhanced Input
Upgrade input handling:
- [ ] Autocompletion for file paths
- [ ] Slash command support (`/help`, `/clear`, `/workers`)
- [ ] Multi-line input mode
- [ ] Persistent command history

### Phase 6: Worker-Specific UI
llm-do specific features (not in Vibe):
- [ ] Worker delegation visualization (show worker call stack)
- [ ] Sandbox path indicators
- [ ] Per-worker approval state display
- [ ] Worker output schema hints

### Phase 7: Styling & Polish
- [ ] TCSS theme with customizable colors
- [ ] Dark/light mode support
- [ ] Consistent spacing and borders
- [ ] Help overlay (keyboard shortcuts)
- [ ] Config option for UI preferences

### Phase 8: Configuration
Add to worker/project config:
- [ ] `ui.theme` - Color theme selection
- [ ] `ui.show_tool_args` - Verbosity control
- [ ] `ui.approval_timeout` - Auto-deny after N seconds
- [ ] `ui.streaming_batch_size` - Chunk batching for smooth render

## Architecture

### Event Flow (Final)
```
run_worker_async()
  → message_callback(events)
    → LlmDoEventHandler.handle_event()
      → match event type:
        → ToolCallEvent: mount ToolCallMessage
        → ToolResultEvent: mount ToolResultMessage
        → TextEvent: append to AssistantMessage
        → WorkerStartEvent: mount WorkerDelegationMessage
        → etc.

ApprovalToolset.needs_approval() → needs_approval
  → async_approval_callback(request)
    → app.push_screen(ApprovalDialog)
    → user interacts (keyboard)
    → ApprovalDialog posts ApprovalGranted/Rejected
    → callback returns ApprovalDecision
```

### Widget Hierarchy (Target)
```
LlmDoApp
├── Header (optional - app title, worker name)
├── MessageContainer (scrollable)
│   ├── UserMessage
│   ├── AssistantMessage (streaming)
│   ├── ToolCallMessage
│   ├── ToolResultMessage
│   ├── WorkerDelegationMessage
│   └── ErrorMessage
├── StatusBar
│   ├── ModeIndicator
│   ├── ModelInfo
│   └── WorkerInfo
└── InputArea
    ├── PromptIndicator (>)
    └── TextInput (with history, completion)

Modal Screens:
├── ApprovalDialog
├── HelpScreen
└── ConfigScreen (future)
```

## Current State
Not started. Waiting for 02-textual-ui-integration.

## Notes
- Vibe's `agent.py` is 36KB - we don't need their agent loop, just UI
- Their tool discovery is directory-based; ours is config-driven (keep ours)
- Consider extracting reusable widgets to a separate package later
- MCP integration could come as future task (additive)
- Middleware (turn/cost limits) could be separate future task

## References
- Mistral Vibe repo: https://github.com/mistralai/mistral-vibe
- Vibe UI code: `vibe/cli/textual_ui/`
- Vibe widgets: `vibe/cli/textual_ui/widgets/`
- Vibe approval: `vibe/cli/textual_ui/approval_app.py`
- Textual docs: https://textual.textualize.io/
