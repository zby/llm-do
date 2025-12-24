# Textual CLI Port + Remove Legacy Runtime

## Prerequisites
- [x] 60-context-runtime-llm-run (complete)
- [x] 80-llm-run-streaming-events (complete)

## Goal
Port the Textual CLI to the new context-centric runtime, then remove the legacy runtime/CLI paths so there is only one current architecture.

## Approach
Phased approach to reduce risk:
1. **Phase A**: Validate `llm-run` is feature-complete
2. **Phase B**: Port Textual UI to new runtime
3. **Phase C**: Cleanup legacy code

---

## Phase A: Validate llm-run Features

Ensure all use cases work with the new runtime before porting Textual.

### Feature Parity Checklist
- [ ] All example workers execute correctly
- [ ] Tool approval patterns work (`requires_approval`, `--approve-all`)
- [ ] Worker-calls-worker pattern works
- [ ] Code entry pattern works (Python tool as entry point)
- [ ] Error handling and reporting is adequate
- [ ] `-v` shows tool calls in real-time
- [ ] `-vv` streams LLM text output
- [ ] `--json` outputs parseable event stream

### Missing Features (if any)
- [ ] Identify gaps vs old `llm-do` CLI
- [ ] Implement missing features

---

## Phase B: Port Textual UI

Once `llm-run` is validated, port the interactive UI.

### Textual UI Port
- [ ] Port Textual CLI to use `llm_do/ctx_runtime` execution flow
- [ ] Connect `on_event` callback to Textual UI for real-time updates
- [ ] Wire interactive approval prompts (replaces headless PermissionError)
- [ ] Verify approvals/tool loading behave identically in the UI

### CLI Structure Decision
- [ ] Decide: merge into `llm-do` or keep `llm-run` separate?
  - Option A: `llm-do` auto-detects TTY (interactive vs headless)
  - Option B: `llm-do` for interactive, `llm-run` for headless (current)

---

## Phase C: Cleanup

### Remove Legacy
- [ ] Remove legacy runtime modules (`llm_do/runtime.py`, etc.)
- [ ] Remove old CLI paths
- [ ] Update imports throughout codebase

### Tests
- [ ] Port `test_cli_async.py` (488 lines) - CLI integration tests
- [ ] Port `test_display_backends.py` (351 lines) - UI backend tests
- [ ] Run `uv run pytest` and fix any breakage

### Documentation
- [ ] Update docs to reference new runtime only
- [ ] Move validated `examples-new/` to `examples/` (replace old examples)

---

## Current Architecture

### Type System
| Type | Purpose |
|------|---------|
| `Context` | Central dispatcher - manages toolsets, depth, model resolution, event emission |
| `WorkerEntry` | LLM-powered worker that IS an AbstractToolset (can be composed into other workers) |
| `ToolEntry` | Wrapper for code entry pattern (Python tool as entry point) |
| `EventCallback` | `Callable[[UIEvent], None]` for real-time progress updates |

### Key APIs
- `build_entry(worker_files, python_files, model, entry_name)` → `ToolEntry | WorkerEntry`
- `Context.from_entry(entry, model, on_event, verbosity)` - creates execution context
- `ctx.run(entry, input_data)` - executes the entry
- `ctx.call(name, args)` - programmatic tool invocation

### Event System
- `on_event: EventCallback` passed to Context, inherited by children
- `verbosity: int` controls detail level (0=quiet, 1=tool events, 2=streaming)
- Events: `ToolCallEvent`, `ToolResultEvent`, `TextResponseEvent`
- Display backends: `HeadlessDisplayBackend`, `JsonDisplayBackend`

## Notes
- Runtime is at `llm_do/ctx_runtime/`
- 59 tests passing in `tests/runtime/`
- Keep old `llm-do` working during Phase A (deprecated but functional)
