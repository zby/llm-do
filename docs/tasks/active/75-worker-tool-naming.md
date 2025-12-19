# Task 75: Simplify Worker Tool Naming

## Goal

Remove the `_worker_` prefix from worker tools so they share names with their workers, and unify the allowed tools list to eliminate special-case handling.

## Current State

Workers get prefixed tool names:
- Worker `summarizer` → tool `_worker_summarizer`
- Prefix defined in `delegation_toolset.py:34`: `_WORKER_TOOL_PREFIX = "_worker_"`

This creates unnecessary complexity:
- Two separate allowed lists: regular tools + configured workers
- Prefix detection via `_is_worker_tool()`
- Name conversion functions: `_tool_name_from_worker()`, `_worker_name_from_tool()`
- Reserved tools (`worker_call`, `worker_create`) need special handling
- Separate approval branch for worker tools in `needs_approval()`

## New Design

### Tool Naming
Worker tools have the **same name as the worker**:
- Worker `summarizer` → tool `summarizer`
- Worker `code_analyzer` → tool `code_analyzer`

### Configuration (No Schema Change)
This task does **not** introduce a new config schema. Workers continue to be configured via the existing `toolsets.delegation` config in `WorkerDefinition`. The simplification is internal:
- Worker names in delegation config map directly to tool names (no prefix transformation)
- The existing `toolsets.delegation.{worker_name}` structure remains unchanged

### Tool vs Internal Function Naming

There are two distinct concepts:

1. **`worker_call` (LLM tool)**: Exposed to the LLM, restricted to session-generated workers only
2. **`_invoke_worker()` (internal function)**: Internal mechanism that actually executes any worker

The LLM-facing `worker_call` tool is for dynamically calling workers created during the session. Configured workers get their own dedicated tools (named same as worker).

### worker_call Restricted to Session-Generated Workers
The `worker_call` tool should **only** allow calling session-generated workers. Configured workers are called via their direct tool names (same as worker name).

This prevents allowlist bypass - if `worker_call` could call any configured worker, it would circumvent the per-worker allowlist.

```python
def needs_approval(self, ctx, name, tool_args):
    if name == "worker_call":
        worker_name = tool_args.get("worker")
        if not self._is_generated_worker(ctx, worker_name):
            # Block - not a session-generated worker
            return ApprovalResult.blocked(
                f"worker_call only supports session-generated workers. "
                f"Worker '{worker_name}' is not available."
            )
        return ApprovalResult.pre_approved()
    # ... other tool handling
```

### How Workers Are Called

| Worker Type | LLM Tool Name | Approval |
|-------------|---------------|----------|
| Configured (`summarizer` in config) | `summarizer` | needs_approval |
| Session-generated (via `worker_create`) | `worker_call` with `worker=name` | pre_approved |

Both ultimately use `_invoke_worker()` internally, but the LLM sees different tool interfaces.

## Implementation Steps

### 1. Remove prefix handling (`delegation_toolset.py`)
- [ ] Remove `_WORKER_TOOL_PREFIX` constant
- [ ] Remove `_tool_name_from_worker()` function
- [ ] Remove `_worker_name_from_tool()` function
- [ ] Remove `_is_worker_tool()` function
- [ ] Update tool registration to use worker name directly

### 2. Update worker_call approval (`delegation_toolset.py`)
- [ ] Remove the worker tool branch (prefix-based detection)
- [ ] Update `worker_call` to pre-approve session-generated workers only
- [ ] Block `worker_call` for configured workers (must use direct tool)
- [ ] Keep `worker_create` handling as-is

### 3. Add name collision validation (`delegation_toolset.py`)
- [ ] Define reserved tool names: `worker_call`, `worker_create`
- [ ] Validate at toolset init that no worker name collides with reserved names
- [ ] Raise clear error if collision detected
- [ ] Add tests for collision detection

### 4. Update all affected files
Files referencing `_worker_` prefix:
- [ ] `llm_do/delegation_toolset.py` - main changes
- [ ] `llm_do/base.py`
- [ ] `llm_do/types.py`
- [ ] `llm_do/cli_async.py`
- [ ] `llm_do/runtime.py`
- [ ] `llm_do/registry.py`
- [ ] `llm_do/__init__.py`
- [ ] `llm_do/ui/app.py`

### 5. Update tests
- [ ] `tests/test_worker_delegation.py`
- [ ] `tests/test_integration_live.py`
- [ ] `tests/test_nested_worker_hang.py`
- [ ] `tests/test_pydanticai_base.py`
- [ ] `tests/test_cli_async.py`
- [ ] `tests/test_workshop.py`
- [ ] `tests/test_bootstrapper.py`
- [ ] `tests/test_examples.py`
- [ ] `tests/test_custom_tools.py`
- [ ] `tests/test_model_compat.py`
- [ ] `tests/conftest.py`
- [ ] `examples/whiteboard_planner/tests/test_whiteboard_example.py`
- [ ] Add tests for `worker_call` blocking configured workers
- [ ] Add tests for name collision validation

### 6. Update documentation
- [ ] Update docs referencing `_worker_` prefix (exclude archived docs)

## Name Collision Rules

Workers share namespace with other tools. Concrete validation:

1. **Reserved names** (always blocked): `worker_call`, `worker_create`
2. **Validation timing**: At DelegationToolset initialization
3. **Error behavior**: Raise `ValueError` with clear message
4. **Built-in tool collisions**: If a worker name matches a built-in tool from another toolset (e.g., `shell`, `read_file`), the worker tool shadows it within that agent. This is the user's responsibility to avoid via naming conventions.

## Acceptance Criteria

- [ ] Worker tools named same as worker (no prefix)
- [ ] `worker_call` pre-approves session-generated workers
- [ ] `worker_call` blocks configured workers (must use direct tool)
- [ ] Name collision validation for reserved names
- [ ] All tests pass
- [ ] No `_worker_` prefix in source code or non-archived docs

## Related

- Task 70: Simplify Worker Invocation (CLI syntax, different concern)
