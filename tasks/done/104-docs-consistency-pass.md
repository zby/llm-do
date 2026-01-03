# Docs Consistency Pass

## Prerequisites
- [x] None.

## Goal
Testing guidance and UI documentation are aligned and have a clear source of truth.

## Tasks
- [x] Align README and AGENTS on the preferred test command.
- [x] Update `docs/ui.md` to match the Textual backend.
- [x] Decide where UI documentation should live to avoid drift.

## Current State
Completed.

## Notes
- Origin: examples/docs review notes.

## Implementation Summary

1. **Test command alignment**:
   - Standardized on `uv run pytest` as the canonical test command
   - Updated AGENTS.md line 18 (was `.venv/bin/pytest`)
   - README.md already used `uv run pytest`

2. **docs/ui.md verification**:
   - Already updated in task 102 to reflect Textual backend
   - Verified no stale Rich/RichDisplayBackend references remain
   - Correctly documents TextualDisplayBackend, JsonDisplayBackend, HeadlessDisplayBackend
   - approval_request event kind documented as TUI-only

3. **UI documentation location decision**:
   - Kept in `docs/ui.md` as the single source of truth
   - Central docs location is appropriate for architecture documentation
   - Code in `llm_do/ui/` has inline docstrings for implementation details
