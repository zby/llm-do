# Textual CLI Port + Remove Legacy Runtime

## Prerequisites
- [x] 60-context-runtime-llm-run (complete)
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

### Cleanup
- [ ] Remove legacy runtime modules and related CLI paths
- [ ] Update docs and examples to reference the new runtime only
- [ ] Move validated `examples-new/` to `examples/` (replace old examples)

### Tests (Deferred from Task 60)
- [ ] Port `test_cli_async.py` (488 lines) - CLI integration tests
- [ ] Port `test_display_backends.py` (351 lines) - UI backend tests
- [ ] Run `uv run pytest` and fix any breakage

## Current State
Ready to start. Task 60 complete - `llm_do/ctx_runtime` + `llm-run` headless CLI are implemented.

### Type System (from task 60)
The new runtime uses 3 core types:

| Type | Purpose |
|------|---------|
| **ToolsetToolEntry** | Any tool (from FunctionToolset, ShellToolset, WorkerToolset, etc.) |
| **WorkerEntry** | LLM-powered worker that can call tools |
| **WorkerToolset** | Adapter wrapping WorkerEntry as AbstractToolset |

All tools are unified as `ToolsetToolEntry` - the separate `ToolEntry` type was removed.

### Key APIs
- `build_entry(worker_files, python_files, model, entry_name)` - builds entry (worker or tool) with all toolsets resolved
  - Returns `(entry, available_tools)` tuple
  - For tool entries, `available_tools` contains workers the tool can call
- Workers-as-toolsets: pass multiple `.worker` files to CLI, they can reference each other by name
- Tool entry pattern: Python function from FunctionToolset can be entry point, gets access to workers

## Notes
- Runtime is at `llm_do/ctx_runtime/` (named to avoid conflict with existing `llm_do/runtime.py`)
- Keep this phase focused: once Textual CLI is ported, delete old runtime code.
- The headless `llm-run` from task 60 raises `PermissionError` for unapproved tools; this task adds interactive prompts.
- 58 tests passing in `tests/runtime/`
