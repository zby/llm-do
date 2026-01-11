# Remove ToolInvocable and backwards compatibility aliases

## Status
completed

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
  - `llm_do/runtime/worker.py` - ToolInvocable class (removed)
  - `llm_do/runtime/registry.py` - python_tool_map logic, InvocableRegistry alias (removed)
  - `llm_do/runtime/contracts.py` - Invocable = Entry alias (removed)
  - `llm_do/runtime/__init__.py` - exports of deprecated symbols (removed)
  - `llm_do/__init__.py` - top-level exports (updated)
  - `examples/pitchdeck_eval_code_entry/tools.py` - migrated to @entry pattern
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
- [x] Migrate `pitchdeck_eval_code_entry` example from @tools.tool to @entry pattern
- [x] Remove ToolInvocable class from worker.py (~45 lines)
- [x] Remove python_tool_map logic from registry.py (~15 lines)
- [x] Remove InvocableRegistry alias and build_invocable_registry wrapper from registry.py
- [x] Remove Invocable alias from contracts.py
- [x] Update all imports in llm_do/__init__.py and llm_do/runtime/__init__.py
- [x] Update CLI (main.py) to use EntryRegistry/build_entry_registry directly
- [x] Update/remove tests that depend on ToolInvocable
- [x] Run lint, typecheck, tests

## Current State
Implementation complete. All tests pass.

**Net result: -143 lines** (76 added, 219 removed)

Changes:
- Migrated pitchdeck_eval_code_entry example to use @entry decorator
- Removed ToolInvocable class from worker.py
- Removed _get_tool_names and python_tool_map logic from registry.py
- Removed all backwards compat aliases (Invocable, InvocableRegistry, build_invocable_registry)
- Updated CLI to use EntryRegistry/build_entry_registry directly
- Updated all tests to use new names
- Rewrote ToolInvocable-specific tests to use EntryFunction

## Notes
- WorkerToolset is unrelated - it exposes a Worker as a tool for another agent, not as an entry point
- The pitchdeck example signature changed from `(run_ctx: RunContext[WorkerRuntime], input)` to `(input, deps: WorkerRuntime)`
- This completes the simplification that task 212 started but didn't finish
