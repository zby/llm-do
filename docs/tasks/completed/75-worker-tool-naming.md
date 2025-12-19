# Task 75: Simplify Worker Tool Naming

## Status: COMPLETED

## Goal

Remove the `_worker_` prefix from worker tools so they share names with their workers, and unify the allowed tools list to eliminate special-case handling.

## What Changed

### Tool Naming
Worker tools now have the **same name as the worker** (no prefix):
- Worker `summarizer` → tool `summarizer`
- Worker `code_analyzer` → tool `code_analyzer`

### worker_call Restricted to Session-Generated Workers
The `worker_call` tool now **only** allows calling session-generated workers:
- **Pre-approved**: If target worker was generated this session
- **Blocked**: For configured workers (use direct tool instead)

This prevents allowlist bypass.

### How Workers Are Called

| Worker Type | LLM Tool Name | Approval |
|-------------|---------------|----------|
| Configured (`summarizer` in config) | `summarizer` | needs_approval |
| Session-generated (via `worker_create`) | `worker_call` with `worker=name` | pre_approved |

### Internal Helper
Added `_invoke_worker()` helper method that both configured worker tools and `worker_call` use internally.

## Implementation Summary

### 1. Remove prefix handling (`delegation_toolset.py`)
- [x] Remove `_WORKER_TOOL_PREFIX` constant
- [x] Remove `_tool_name_from_worker()` function
- [x] Remove `_worker_name_from_tool()` function
- [x] Remove `_is_worker_tool()` function
- [x] Update tool registration to use worker name directly

### 2. Update worker_call approval (`delegation_toolset.py`)
- [x] Remove the worker tool branch (prefix-based detection)
- [x] Update `worker_call` to pre-approve session-generated workers only
- [x] Block `worker_call` for configured workers (must use direct tool)
- [x] Keep `worker_create` handling as-is

### 3. Extract `_invoke_worker()` helper (`delegation_toolset.py`)
- [x] Create `_invoke_worker(worker_name, input, attachments)` internal method
- [x] Move worker execution logic from individual tool handlers into this helper
- [x] Both configured worker tools and `worker_call` use this helper

### 4. Add registry.is_generated() method
- [x] Added `is_generated(name)` method to WorkerRegistry
- [x] Used by delegation_toolset to check session-generated workers

### 5. Update tests
- [x] `tests/test_worker_delegation.py` - updated tool name format
- [x] `tests/test_integration_live.py` - updated comment
- [x] `tests/test_nested_worker_hang.py` - updated tool name
- [x] `tests/test_pydanticai_base.py` - updated assertion
- [x] Add test for `worker_call` blocking configured workers

## Acceptance Criteria

- [x] Worker tools named same as worker (no prefix)
- [x] `_invoke_worker()` helper extracts common worker execution logic
- [x] `worker_call` pre-approves session-generated workers
- [x] `worker_call` blocks non-session-generated workers
- [x] All tests pass (196 tests)
- [x] No `_worker_` prefix pattern in source code

## Files Modified

- `llm_do/delegation_toolset.py` - main implementation
- `llm_do/registry.py` - added `is_generated()` method
- `tests/test_worker_delegation.py`
- `tests/test_pydanticai_base.py`
- `tests/test_nested_worker_hang.py`
- `tests/test_integration_live.py`

## Related

- Task 70: Simplify Worker Invocation (CLI syntax, different concern)
