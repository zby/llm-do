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
1. **PydanticAI Agent** - Use `event_stream_handler` callback
2. **Context.call()** - Emit events for programmatic tool calls
3. **WorkerEntry.call()** - Emit events for worker execution

### CLI Flags
```bash
llm-run [files...] "prompt" [options]
  -v, --verbose       Show tool calls and progress
  -vv                 Also stream LLM text responses
  --json              Output events as JSON lines (for piping)
  --quiet             Suppress all output except final result (default)
```

### Implementation Approach

#### Option A: Callback-based (like original CLI)
Pass `message_callback` through Context to WorkerEntry:
```python
ctx = Context.from_entry(
    entry,
    model=model,
    message_callback=lambda events: display(events),
)
```

#### Option B: AsyncIO Queue (cleaner separation)
Use an async queue for events:
```python
event_queue: asyncio.Queue[UIEvent] = asyncio.Queue()

async def run_with_events():
    ctx = Context.from_entry(entry, model=model)
    task = asyncio.create_task(ctx.run(entry, input_data))

    async for event in ctx.events():  # New async iterator
        display(event)

    return await task
```

#### Option C: Hybrid (recommended)
- Use PydanticAI's `event_stream_handler` for agent events
- Emit custom events for `ctx.call()` and worker delegation
- Display backend renders events to console

## Tasks

### Phase 1: Event Infrastructure
- [ ] Add `event_callback` parameter to `Context.__init__()`
- [ ] Wire PydanticAI `event_stream_handler` in `WorkerEntry._build_agent()`
- [ ] Emit events from `Context.call()` for tool invocations
- [ ] Emit events from `Context._execute()` for entry execution

### Phase 2: CLI Integration
- [ ] Add `-v/--verbose` flag to `llm-run`
- [ ] Add `--json` flag for JSON event output
- [ ] Create display backend for `llm-run` (reuse or adapt from `llm_do.ui.display`)
- [ ] Wire event callback to display backend in `run()`

### Phase 3: Streaming Support
- [ ] Add `-vv` support for text streaming
- [ ] Handle `TextResponseEvent` deltas properly
- [ ] Test with models that support streaming

### Phase 4: Testing
- [ ] Unit tests for event emission
- [ ] Integration tests for CLI flags
- [ ] Test JSON output format

## Files to Modify

- `llm_do/ctx_runtime/ctx.py` - Add event_callback, emit events
- `llm_do/ctx_runtime/entries.py` - Wire event_stream_handler in WorkerEntry
- `llm_do/ctx_runtime/cli.py` - Add CLI flags, display backend

## Acceptance Criteria
- [ ] `llm-run -v example.worker "prompt"` shows tool calls as they happen
- [ ] `llm-run -vv example.worker "prompt"` streams LLM text output
- [ ] `llm-run --json example.worker "prompt"` outputs JSON event stream
- [ ] Events include: tool_call, tool_result, text_delta, text_complete, error
- [ ] Matches original `llm-do` CLI behavior for equivalent flags

## Notes
- Consider whether to reuse `llm_do.ui.events` or create simpler event types
- JSON output should be newline-delimited for easy parsing
- Streaming requires model support; gracefully degrade for non-streaming models
