# Textual CLI Port + Remove Legacy Runtime

## Prerequisites
- [x] 60-context-runtime-llm-run (complete)
- [x] 80-llm-run-streaming-events (complete)
- [ ] Decision to switch interactive UI to the new runtime

## Goal
Port the Textual CLI to the new context-centric runtime, then remove the legacy runtime/CLI paths so there is only one current architecture.

## Tasks

### CLI Consolidation
- [ ] Consolidate `llm-run` into `llm-do` (deferred from task 60)
  - Single entry point with mode detection or subcommands
  - Preserve all flags from both CLIs

### Textual UI Port
- [ ] Port Textual CLI to use `llm_do/ctx_runtime` execution flow
- [ ] Verify approvals/tool loading behave identically in the UI
- [ ] Wire interactive approval prompts (replaces headless PermissionError)
- [ ] Connect `on_event` callback to Textual UI for real-time updates

### Cleanup
- [ ] Remove legacy runtime modules and related CLI paths
- [ ] Update docs and examples to reference the new runtime only
- [ ] Move validated `examples-new/` to `examples/` (replace old examples)

### Tests (Deferred from Task 60)
- [ ] Port `test_cli_async.py` (488 lines) - CLI integration tests
- [ ] Port `test_display_backends.py` (351 lines) - UI backend tests
- [ ] Run `uv run pytest` and fix any breakage

## Current State
Ready to start. Tasks 60 and 80 complete - `llm_do/ctx_runtime` + `llm-run` CLI with streaming events are implemented.

### Type System
The new runtime uses these core types:

| Type | Purpose |
|------|---------|
| `Context` | Central dispatcher - manages toolsets, depth, model resolution, event emission |
| `WorkerEntry` | LLM-powered worker that IS an AbstractToolset (can be composed into other workers) |
| `ToolEntry` | Wrapper for code entry pattern (Python tool as entry point) |
| `EventCallback` | `Callable[[UIEvent], None]` for real-time progress updates |

### Key APIs
- `build_entry(worker_files, python_files, model, entry_name)` → `ToolEntry | WorkerEntry`
  - Returns entry with `toolsets` attribute populated
  - Workers can reference other workers by name in their toolsets
- `Context.from_entry(entry, model, on_event, verbosity)` - creates execution context
- `ctx.run(entry, input_data)` - executes the entry
- `ctx.call(name, args)` - programmatic tool invocation (searches across toolsets)

### Event System
- `on_event: EventCallback` passed to Context, inherited by children
- `verbosity: int` controls detail level (0=quiet, 1=tool events, 2=streaming)
- Events emitted: `ToolCallEvent`, `ToolResultEvent`, `TextResponseEvent`
- Display backends: `HeadlessDisplayBackend`, `JsonDisplayBackend`

## Notes
- Runtime is at `llm_do/ctx_runtime/` (named to avoid conflict with existing `llm_do/runtime.py`)
- Keep this phase focused: once Textual CLI is ported, delete old runtime code
- The headless `llm-run` raises `PermissionError` for unapproved tools; this task adds interactive prompts
- 59 tests passing in `tests/runtime/`
- CallTrace removed in favor of event-based progress tracking
