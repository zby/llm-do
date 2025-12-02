# SimpleApprovalToolset Enhancement Proposal

## Context

After implementing `sandbox-toolset-separation-v2.md`, we noticed that `CustomToolset` and potentially other toolsets could use `SimpleApprovalToolset` from `pydantic-ai-blocking-approval` instead of implementing their own `needs_approval()` method.

## Current State

`SimpleApprovalToolset` currently supports:
```python
config={
    "tool_name": {
        "pre_approved": True,  # Skip approval
    }
}
```

It only returns `True` (needs approval) or `False` (pre-approved).

## What We Need

### For CustomToolset

Our current `needs_approval()` does:
1. **Blocking**: `allowed: False` raises `PermissionError` → **Replace with whitelist in `get_tools()`**
2. **Pre-approval**: `approval_required: False` skips approval → **Use `SimpleApprovalToolset`**
3. **Custom description**: Returns `{"description": ...}` → **Use default description**

### For DelegationToolset

1. **Blocking**: `allow_workers` check raises `PermissionError` if worker not in list
2. **Custom description**: Returns `{"description": f"Delegate to worker: {target}"}`

These depend on `tool_args`, so keep custom `needs_approval()`.

### For ShellToolset

1. **Pattern-based rules**: Complex matching logic depends on command string
2. **Sandbox path validation**: Checks args against allowed sandboxes

These depend on `tool_args`, so keep custom `needs_approval()`.

## Proposed Approach

**No enhancement to SimpleApprovalToolset needed.** It already supports `pre_approved`:

```python
config={
    "tool_a": {},                        # Exposed, requires approval
    "tool_b": {"pre_approved": True},    # Exposed, pre-approved
    # tool_c not in config = not exposed
}
```

### Whitelist Model

- `get_tools()` only returns tools that have a config entry
- No `allowed` field needed - absence from config means "not allowed"
- Secure by default: tools must be explicitly whitelisted

### Separation of Concerns

1. **Whitelisting**: Inner toolset's `get_tools()` filters to only tools present in config
2. **Pre-approval**: `SimpleApprovalToolset` handles approval based on `pre_approved`
3. **Description**: Uses default from `_prompt_for_approval()`

This keeps `pydantic-ai-blocking-approval` focused on approval logic, not access control.

## Action Items

1. Refactor `CustomToolset` to:
   - Filter `get_tools()` to only return tools present in config (whitelist)
   - Use `SimpleApprovalToolset` wrapper for approval logic
   - Remove `allowed` field and custom `needs_approval()` implementation
2. Keep `DelegationToolset` and `ShellToolset` with custom `needs_approval()` (arg-dependent logic)
