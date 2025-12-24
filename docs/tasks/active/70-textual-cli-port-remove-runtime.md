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
- [x] All example workers execute correctly
- [x] Tool approval patterns work (`requires_approval`, `--approve-all`, `_approval_config`)
- [x] Worker-calls-worker pattern works
- [x] Code entry pattern works (Python tool as entry point)
- [x] Error handling and reporting is adequate
- [x] `-v` shows tool calls in real-time
- [x] `-vv` streams LLM text output
- [x] `--json` outputs parseable event stream

### Missing Features (if any)
- [x] Identify gaps vs old `llm-do` CLI
- [x] ApprovalToolset wrapping (secure by default)
- [x] Event emission from `ctx.call()` for code entry visibility

---

## Phase B: Port Textual UI

Once `llm-run` is validated, port the interactive UI.

### Textual UI Port
- [x] Port Textual CLI to use `llm_do/ctx_runtime` execution flow
- [x] Connect `on_event` callback to Textual UI for real-time updates
- [x] Wire interactive approval prompts (async callback via queue)
- [x] Verify approvals/tool loading behave identically in the UI (tested with approvals_demo)

### CLI Structure Decision
- [x] Decide: merge into `llm-do` or keep `llm-run` separate?
  - **Chosen**: `llm-run` auto-detects TTY (TUI mode by default when TTY available)
  - `--headless` flag to force headless mode
  - `--tui` flag to force TUI mode

---

## Phase C: Cleanup

### Remove Legacy
- [x] Remove legacy runtime modules (`llm_do/runtime.py`, etc.)
- [x] Remove old CLI paths (kept `llm-do-oauth` as standalone utility)
- [x] Update imports throughout codebase

### Tests
- [x] Remove legacy tests (test_cli_async.py, test_config_overrides.py, etc.)
- [x] Keep shared module tests (display backends, shell, filesystem, oauth)
- [x] Run `uv run pytest` - 219 tests passing

### Documentation
- [ ] Update docs to reference new runtime only
- [x] Move validated `examples-new/` to `examples/` (replaced old examples)

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
- `build_entry(worker_files, python_files, model, entry_name, set_overrides)` → `ToolEntry | WorkerEntry`
- `Context.from_entry(entry, model, on_event, verbosity)` - creates execution context
- `ctx.run(entry, input_data)` - executes the entry
- `ctx.call(name, args)` - programmatic tool invocation

### CLI Override Support
The `--set KEY=VALUE` flag allows overriding worker config at runtime:
- Simple values: `--set model=openai:gpt-4o`
- Nested paths: `--set toolsets.shell.timeout=60`
- JSON values: `--set tags='["a","b"]'`

Overrides are applied to worker file frontmatter before parsing.

### Event System
- `on_event: EventCallback` passed to Context, inherited by children
- `verbosity: int` controls detail level (0=quiet, 1=tool events, 2=streaming)
- Events: `ToolCallEvent`, `ToolResultEvent`, `TextResponseEvent`
- Display backends: `HeadlessDisplayBackend`, `JsonDisplayBackend`

## Design Decisions

### No Built-in Jinja Templating
The old runtime supported Jinja2 templating in `.worker` file instructions. The new runtime intentionally omits this:

- **Code entry pattern is the escape hatch**: Users who need templating can use a Python code entry point and use any templating engine they prefer (Jinja, Mako, f-strings, etc.)
- **Simpler runtime**: No templating complexity in the core runtime
- **More flexible**: Not locked into Jinja syntax

Example pattern for templating:
```python
@tools.tool
async def main(ctx: RunContext[Context], input: str) -> str:
    from jinja2 import Template
    template = Template(Path("prompts/evaluate.j2").read_text())
    prompt = template.render(input=input)
    return await ctx.deps.call("evaluator", {"input": prompt})
```

### Secure by Default Approvals
All toolsets are wrapped with `ApprovalToolset`:
- Toolsets with `needs_approval()` method use that (FileSystemToolset, ShellToolset)
- Toolsets with `_approval_config` use config-based per-tool pre-approval
- Other toolsets require approval for all tools unless `--approve-all`

## Notes
- Runtime is at `llm_do/ctx_runtime/`
- 73 tests passing in `tests/runtime/`
- Keep old `llm-do` working during Phase A (deprecated but functional)

## Implementation Notes (Phase B)

### TUI Mode Integration
Added TUI mode to `llm_do/ctx_runtime/cli.py`:
- `_run_tui_mode()` - async function that sets up Textual app
- Auto-detects TTY and defaults to TUI mode when available
- Uses `--headless` to force headless mode, `--tui` to force TUI mode

### Event Flow
1. `on_event` callback forwards `UIEvent` to `event_queue`
2. `LlmDoApp` consumes events and updates UI via `MessageContainer`
3. Events also logged to `RichDisplayBackend` for post-TUI display

### Approval Flow (TUI Mode)
1. `ApprovalToolset` calls async `tui_approval_callback`
2. Callback sends `ApprovalRequestEvent` to `event_queue`
3. TUI displays approval prompt with key bindings (a/s/d)
4. User decision sent to `approval_queue`
5. Callback awaits and returns `ApprovalDecision`

### Key Files Modified
- `llm_do/ctx_runtime/cli.py` - added TUI mode, async approval callback
- Reuses existing `llm_do/ui/app.py` (LlmDoApp)
- Reuses existing `llm_do/ui/parser.py` (parse_approval_request)

## Implementation Notes (Phase C)

### Files Removed
Legacy runtime modules (total ~5000 lines):
- `llm_do/base.py` - old WorkerRegistry, WorkerDefinition
- `llm_do/cli_async.py` - old CLI (905 lines)
- `llm_do/custom_toolset.py` - old toolset pattern
- `llm_do/delegation_toolset.py` - old delegation pattern
- `llm_do/execution.py` - old execution engine
- `llm_do/registry.py` - old registry
- `llm_do/runtime.py` - old runtime (613 lines)
- `llm_do/tool_context.py` - old context
- `llm_do/tool_registry.py` - old tool registry
- `llm_do/toolset_loader.py` - old loader
- `llm_do/types.py` - old types
- `llm_do/attachments/` - attachment handling (not needed in new runtime)

Legacy tests removed:
- `tests/test_cli_async.py`, `test_custom_tools.py`
- `tests/test_server_side_tools.py`, `test_tool_entry_point.py`
- `tests/test_worker_delegation.py`, `tests/test_workshop.py`
- `tests/test_pydanticai_base.py`, `tests/test_bootstrapper.py`
- `tests/test_examples.py`, `tests/test_pydanticai_integration.py`

### Files Kept
Shared modules used by new runtime:
- `llm_do/ui/` - Textual UI components, display backends, events
- `llm_do/shell/` - ShellToolset with approval support
- `llm_do/filesystem_toolset.py` - FileSystemToolset with approval support
- `llm_do/model_compat.py` - model selection and validation
- `llm_do/oauth/` - OAuth credential management
- `llm_do/config_overrides.py` - `--set KEY=VALUE` CLI override support

### New Files
- `llm_do/oauth_cli.py` - standalone OAuth CLI (extracted from old cli_async.py)

### Entry Points
- `llm-run` - main CLI for running workers (TUI or headless)
- `llm-do-oauth` - OAuth credential management

### Package Version
Updated from 0.2.0 to 0.3.0
