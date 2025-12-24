# llm-run Streaming Events and Intermediate Results

## Prerequisites
- [x] Task 60: Context Runtime + llm-run CLI

## Goal
Add streaming events and intermediate result emission to the `llm-run` CLI, matching the capabilities of the original `llm-do` CLI even in headless mode.

## Current State
The `llm-run` CLI currently:
- Only outputs the final result
- No progress indication during execution
- No visibility into tool calls as they happen
- `--trace` flag shows execution trace only after completion

The original `llm-do` CLI provides:
- `-v` flag for progress updates (tool calls, worker delegations)
- `-vv` flag for streaming text responses
- `--json` flag for machine-readable event stream
- Real-time visibility into agent execution

## Design

### Event Types
Reuse existing `llm_do.ui.events` where applicable:
- `TextResponseEvent` - LLM text output (delta/complete)
- `ToolCallEvent` - Tool invocation started
- `ToolResultEvent` - Tool completed with result
- `StatusEvent` - Progress/status updates
- `ErrorEvent` - Errors during execution

### Integration Points
1. **PydanticAI Agent** - Use `run_stream()` for text streaming
2. **WorkerEntry._emit_tool_events()** - Emit events after agent execution
3. **Context.on_event** - Callback for event delivery to display backend

### CLI Flags
```bash
llm-run [files...] "prompt" [options]
  -v, --verbose       Show tool calls and progress
  -vv                 Also stream LLM text responses
  --json              Output events as JSON lines (for piping)
  --quiet             Suppress all output except final result (default)
```

## Tasks

### Phase 1: Event Infrastructure
- [x] Add `on_event` callback parameter to `Context.__init__()`
- [x] Add `verbosity` parameter to Context for streaming control
- [x] Child contexts inherit event callbacks and verbosity
- [x] WorkerEntry emits ToolCallEvent/ToolResultEvent via `_emit_tool_events()`

### Phase 2: CLI Integration
- [x] Add `-v/--verbose` flag to `llm-run` (count action for -v/-vv)
- [x] Add `--json` flag for JSON event output
- [x] Reuse `HeadlessDisplayBackend` and `JsonDisplayBackend` from `llm_do.ui.display`
- [x] Wire event callbacks to display backend in `run()`

### Phase 3: Streaming Support
- [x] Add `-vv` support for text streaming via `verbosity` parameter
- [x] Add `_run_streaming()` to `WorkerEntry` using PydanticAI `run_stream()`
- [x] Emit `TextResponseEvent` deltas during streaming
- [x] Graceful degradation: non-streaming when verbosity < 2

### Phase 4: Testing
- [x] Unit tests for event emission (`TestContextEventCallback`, `TestWorkerEntryToolEvents`)
- [x] Integration tests for CLI (`TestCLIEventIntegration`)
- [x] Streaming event tests (`TestWorkerEntryStreamingEvents`)

## Files Modified

- `llm_do/ctx_runtime/ctx.py` - Add on_event callback, verbosity
- `llm_do/ctx_runtime/entries.py` - Add _emit_tool_events(), _run_streaming()
- `llm_do/ctx_runtime/cli.py` - Add CLI flags, wire display backends
- `tests/runtime/test_events.py` - Comprehensive event tests

## Acceptance Criteria
- [x] `llm-run -v example.worker "prompt"` shows tool calls as they happen
- [x] `llm-run -vv example.worker "prompt"` streams LLM text output
- [x] `llm-run --json example.worker "prompt"` outputs JSON event stream
- [x] Events include: tool_call, tool_result, text_delta, status, error
- [x] Reuses existing `llm_do.ui.events` and display backends

## Implementation Notes
- `on_event: EventCallback` passed to Context and inherited by children
- `verbosity: int` controls streaming level (0=quiet, 1=tool events, 2=streaming)
- `WorkerEntry._emit_tool_events()` extracts events from PydanticAI messages
- `WorkerEntry._run_streaming()` uses PydanticAI `run_stream()` for text deltas
- Removed legacy CallTrace in favor of direct event emission
