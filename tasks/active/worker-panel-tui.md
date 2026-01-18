# Worker Panel for TUI (Option D: Minimal Status Bar + Expandable)

## Status
ready for implementation

## Prerequisites
- [x] none

## Goal
Add a collapsible worker panel to the TUI that shows the current worker call stack as a minimal status bar by default, expandable to show full details (model, tools, prompt, status) via keyboard toggle.

## Context

### Relevant files/symbols
- `llm_do/ui/app.py` - LlmDoApp main orchestration, grid layout
- `llm_do/ui/widgets/messages.py` - existing message widgets (AssistantMessage, ToolCallMessage, etc.)
- `llm_do/ui/events.py` - UIEvent hierarchy
- `llm_do/runtime/call.py` - CallFrame structure (depth, invocation_name, prompt, messages, active_toolsets)
- `llm_do/runtime/worker.py` - Worker definition & execution

### Current TUI layout (3-row grid)
```
┌─────────────────────────────────┐
│        Header (clock)           │
├─────────────────────────────────┤
│     MessageContainer            │  (1fr - scrollable message feed)
├─────────────────────────────────┤
│   ApprovalPanel (conditional)   │
│   TextArea user input           │
├─────────────────────────────────┤
│        Footer (keybindings)     │
└─────────────────────────────────┘
```

### Design: Option D (Minimal + Expandable)

**Collapsed (default):**
```
┌────────────────────────────────────────────────────────────────────────┐
│ llm-do                                                     12:34:56 PM │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  [main:0] Orchestrating document analysis...                           │
│  [analyzer:1] Reading source files...                                  │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│ WORKERS: main:0 → analyzer:1 → summarizer:2 (●●○)         [^W expand] │
├────────────────────────────────────────────────────────────────────────┤
│ > _                                                                    │
└────────────────────────────────────────────────────────────────────────┘
```

**Expanded (^W pressed):**
```
┌────────────────────────────────────────────────────────────────────────┐
│ llm-do                                                     12:34:56 PM │
├────────────────────────────────────────────────────────────────────────┤
│  [main:0] Orchestrating...                                             │
├────────────────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │  WORKER CALL STACK                                                 │ │
│ │──────────────────────────────────────────────────────────────────  │ │
│ │  [0] main            haiku     ●  5 tools   "Analyze auth..."      │ │
│ │   └▶[1] analyzer     gpt-4o    ●  3 tools   "Examine auth.py..."   │ │
│ │      └▶[2] summarizer haiku    ○  1 tool    (pending)              │ │
│ └────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────┤
│ > _                                                                    │
└────────────────────────────────────────────────────────────────────────┘
```

### Data available per worker frame
From `CallFrame`:
- `depth`: int (nesting level, 0 = entry point)
- `invocation_name`: str (worker name)
- `prompt`: str (input text for this invocation)
- `messages`: list (conversation history)
- `active_toolsets`: available tools

From events:
- Status can be derived: `●` active/streaming, `○` pending/waiting
- Model name from worker definition

### Status indicators
- `●` - active (currently processing or streaming)
- `◐` - streaming response
- `○` - pending/waiting for child worker

### How to verify
1. Run a multi-worker example (e.g., `recursive_summarizer`)
2. Verify collapsed status bar shows worker chain with arrows
3. Press `^W` to expand and see full call stack tree
4. Verify status indicators update as workers become active/pending
5. Verify prompt text is truncated appropriately in expanded view

## Decision Record
- Decision: Use Option D (minimal status bar + expandable panel)
- Inputs: Four design options considered (side panel, bottom panel, detailed tree, minimal+expandable)
- Options:
  - A: Side panel with tree - uses horizontal space, always visible
  - B: Collapsible bottom panel with horizontal boxes - takes vertical space
  - C: Detailed expandable tree - very detailed but verbose
  - D: Minimal status bar + expandable - non-intrusive, detail on demand
- Outcome: Option D chosen for best balance of visibility without stealing screen space
- Follow-ups: May add per-worker drill-down in future

## Tasks
- [ ] Create `WorkerStatusBar` widget for collapsed view
  - Show worker chain: `main:0 → analyzer:1 → summarizer:2`
  - Show status indicators: `(●●○)`
  - Show toggle hint: `[^W expand]`
- [ ] Create `WorkerPanel` widget for expanded view
  - Tree structure with indentation showing hierarchy
  - Columns: depth/name, model (short), status, tool count, truncated prompt
- [ ] Add state tracking for active workers
  - Track which workers are in the call stack
  - Track status per worker (active, streaming, pending)
- [ ] Wire up `^W` keyboard binding to toggle expanded/collapsed
- [ ] Integrate into TUI layout
  - Status bar above input area (below messages)
  - Expanded panel replaces/overlays message area or inserts between
- [ ] Add CSS styling for worker panel components
- [ ] Test with recursive_summarizer and other multi-worker examples

## Current State
Task created with full design spec from conversation. Ready for implementation.

## Notes
- The worker panel should update reactively as events come in
- Consider whether expanded view should be a modal overlay or resize the message container
- Prompt text in expanded view should be truncated (e.g., first 30 chars + "...")
- Model names can be shortened: `anthropic:claude-haiku-4-5` → `haiku`
