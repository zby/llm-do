# Rename Entry → Invocable

## Status
ready for implementation

## Prerequisites
- [x] Task 49: Approval Unification (removes `requires_approval` field first)

## Goal
Rename Entry types to Invocable across the codebase. This clarifies that the abstraction represents "something you can invoke" (tool or worker), not an "entrypoint".

## Context
- Relevant files/symbols:
  - `llm_do/ctx_runtime/ctx.py`: `CallableEntry` (protocol)
  - `llm_do/ctx_runtime/entries.py`: `WorkerEntry`, `ToolEntry` (classes)
  - `llm_do/ctx_runtime/discovery.py`: imports/exports WorkerEntry
  - `llm_do/ctx_runtime/__init__.py`: public exports
  - `llm_do/ctx_runtime/cli.py`: uses WorkerEntry, ToolEntry
  - Tests: various test files reference these types
- Related tasks/notes/docs:
  - `docs/tasks/active/47-split-context-class.md` (depends on this task)
  - `docs/tasks/completed/49-approval-unification.md` (prerequisite)
- How to verify:
  - `uv run pytest`

## Decision Record
- Decision: Rename Entry types to Invocable
- Naming mapping:
  - `CallableEntry` (protocol) → `Invocable`
  - `WorkerEntry` (class) → `WorkerInvocable`
  - `ToolEntry` (class) → `ToolInvocable`
  - `entries.py` → `invocables.py`
- Rationale:
  - "Entry" sounds like "entrypoint" or "entry worker"
  - "Invocable" clearly communicates "something you can invoke/call"
  - Matches the unified abstraction for tools and workers

## Tasks
- [ ] Rename `CallableEntry` → `Invocable` in `ctx.py`
- [ ] Rename `entries.py` → `invocables.py`
- [ ] Rename `WorkerEntry` → `WorkerInvocable` in `invocables.py`
- [ ] Rename `ToolEntry` → `ToolInvocable` in `invocables.py`
- [ ] Update `discovery.py` imports/exports
- [ ] Update `__init__.py` exports
- [ ] Update `cli.py` references
- [ ] Update all test files
- [ ] Run `uv run pytest`

## Current State
Task created. Ready to implement.

## Notes
- Pure rename task — no structural or behavioral changes
- Task 47 (Split Context) depends on this for clean naming
