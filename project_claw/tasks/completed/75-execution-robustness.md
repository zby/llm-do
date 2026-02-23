# Execution Robustness Fixes

## Prerequisites
- None

## Goal
Fix remaining issues from `docs/notes/review-execution-py.md` to make agent execution more robust.

## Tasks

### Medium Priority
- [x] Add try/finally around `agent.run()` to ensure `emit_status("end")` is called on exceptions
  - Location: `llm_do/execution.py:293-310`
  - Emits "error" state on failure, "end" on success
- [x] Make `message_callback` exception handling consistent
  - All callbacks now wrapped in try/except with logging
  - Best-effort approach: callbacks never crash execution

### Low Priority
- [x] Handle `all_messages` as property or method
  - Location: `llm_do/execution.py:318-325`
  - Uses `callable()` check to handle both forms
- [x] Add fallback serializer to `format_user_prompt()`
  - Location: `llm_do/execution.py:60-86`
  - Added `_json_default()` handler for Pydantic models, Path, datetime

### Cleanup
- [ ] Archive or delete `docs/notes/review-execution-py.md` after fixes complete

## Current State
All code fixes complete. 193 tests passing.

## Notes
- High-priority issue (sync `asyncio.run()`) was resolved by removing sync API (commit 77fe22d)
- Open questions from review are obsolete (sync API removed)
