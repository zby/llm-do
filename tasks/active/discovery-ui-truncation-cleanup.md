# Discovery and UI Truncation Cleanup

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Reduce duplication in discovery helpers and UI event truncation logic without changing behavior.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/discovery.py` (discover_toolsets_from_module, discover_workers_from_module, discover_entries_from_module)
  - `llm_do/ui/events.py` (InitialRequestEvent._truncate, ToolCallEvent._truncate, ToolResultEvent._truncate_content)
- Related notes (inline summary):
  - Pattern 3: Introduce a shared module discovery helper for Worker/EntryFunction while keeping toolset discovery separate for AbstractToolset error handling.
  - Pattern 9: Extract shared truncation logic into module-level helpers to avoid duplicated methods.
- How to verify / reproduce:
  - `uv run pytest tests/test_display_backends.py`

## Decision Record
- Decision: prefer small shared helpers for duplicated logic, keep existing behavior.
- Inputs: toolset discovery has special error handling; UI truncation logic is duplicated.
- Options: leave as-is vs extract small helpers.
- Outcome: add helper in discovery, module-level truncation helpers in UI events.
- Follow-ups: none.

## Tasks
- [ ] Add a `_discover_from_module(module, target_type)` helper that avoids repeated getattr calls; use it for workers and entries.
- [ ] Keep discover_toolsets_from_module explicit to preserve AbstractToolset error behavior.
- [ ] Add module-level `_truncate(text, max_len)` and `_truncate_content(text, max_len, max_lines)` helpers in ui/events.
- [ ] Update InitialRequestEvent and ToolCallEvent to use shared `_truncate`.
- [ ] Update ToolResultEvent to use `_truncate_content`.

## Current State
Not started.

## Notes
- Avoid double `getattr` in the discovery helper to prevent side effects.
