# Remove ToolInvocable and backwards compatibility aliases

## Status
ready for implementation

## Prerequisites
- [x] 212-simplify-entry-registry (completed - introduced @entry as replacement)
- [x] 214-worker-toolset-adapter (completed - WorkerToolset is separate concern)

## Goal
Complete the simplification started in task 212 by actually removing the deprecated
ToolInvocable class and backwards compatibility aliases (Invocable, InvocableRegistry,
build_invocable_registry) that were kept "for backwards compatibility" but are only
used internally.

The original goal from `docs/notes/simplify-remove-registry.md` was:
> "No special `ToolInvocable` class needed - just a decorator."

Task 212 added @entry but kept all the old code, resulting in +622 lines instead of
a net reduction.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/worker.py` - ToolInvocable class (lines 308-352)
  - `llm_do/runtime/registry.py` - python_tool_map logic, InvocableRegistry alias
  - `llm_do/runtime/contracts.py` - Invocable = Entry alias
  - `llm_do/runtime/__init__.py` - exports of deprecated symbols
  - `llm_do/__init__.py` - top-level exports
  - `examples/pitchdeck_eval_code_entry/tools.py` - only example using ToolInvocable pattern
- Related tasks:
  - `tasks/completed/212-simplify-entry-registry.md`
  - `tasks/completed/214-worker-toolset-adapter.md`
- How to verify:
  - `rg "ToolInvocable|InvocableRegistry|build_invocable_registry" llm_do/` returns no hits
  - `rg "Invocable" llm_do/runtime/contracts.py` returns no hits
  - `uv run pytest` passes
  - `uv run mypy llm_do` passes

## Decision Record
- Decision: Remove all deprecated code in one pass rather than phased deprecation
- Rationale: All usages are internal (tests, CLI, examples) - no external consumers
- Trade-off: Slightly larger diff but cleaner outcome

## Tasks
- [ ] Migrate `pitchdeck_eval_code_entry` example from @tools.tool to @entry pattern
- [ ] Remove ToolInvocable class from worker.py (~45 lines)
- [ ] Remove python_tool_map logic from registry.py (~15 lines)
- [ ] Remove InvocableRegistry alias and build_invocable_registry wrapper from registry.py
- [ ] Remove Invocable alias from contracts.py
- [ ] Update all imports in llm_do/__init__.py and llm_do/runtime/__init__.py
- [ ] Update CLI (main.py) to use EntryRegistry/build_entry_registry directly
- [ ] Update/remove tests that depend on ToolInvocable
- [ ] Run lint, typecheck, tests

## Current State
Task created. Analysis shows ~145 lines can be removed plus test cleanup.

Key insight: The "backwards compatibility" was unnecessary since all consumers are
internal. The @entry decorator is the intended replacement for ToolInvocable.

## Notes
- WorkerToolset is unrelated - it exposes a Worker as a tool for another agent, not as an entry point
- The pitchdeck example signature changes from `(run_ctx: RunContext[WorkerRuntime], input)` to `(input, deps: WorkerRuntime)`
