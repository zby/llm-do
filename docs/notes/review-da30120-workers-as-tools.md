# Review of Commit da30120 - Workers-as-Tools Implementation

## 1. Bug: Missing Worker Allow-List Validation in `needs_approval`

**File:** `llm_do/agent_toolset.py:90-114`

The old `DelegationToolset.needs_approval()` blocked calls to workers not in `allow_workers`:
```python
# Old behavior (removed)
allow_workers = self._config.get("allow_workers", [])
if '*' not in allow_workers and target_worker not in allow_workers:
    return ApprovalResult.blocked(f"Worker '{target_worker}' not in allow_workers list...")
```

The new `AgentToolset.needs_approval()` just returns `needs_approval()` for all agent tools. While `get_tools()` only generates tools for allowed workers, `worker_call` (the generic fallback) doesn't validate against `allow_workers` anymore. A malicious LLM could use `worker_call` to call any worker, bypassing the allowlist.

## 2. Bug: Exception Handling Too Broad

**File:** `llm_do/agent_toolset.py:188-191`

```python
except Exception:
    # Worker not found - skip it
    logger.debug(f"Worker '{worker_name}' not found, skipping tool generation")
    continue
```

This catches **all** exceptions including programming errors, AttributeError, etc. Should catch `FileNotFoundError` or `ValueError` specifically.

## 3. Unused Code: `_worker_descriptions` Cache

**File:** `llm_do/agent_toolset.py:62, 194`

The `_worker_descriptions` dict is populated in `get_tools()` but never read. It could enhance `get_approval_description()` but isn't used.

## 4. Backward Compatibility Issue: Import Path Changed

**File:** Deleted `llm_do/delegation_toolset.py`

Code using `from llm_do.delegation_toolset import DelegationToolset` will fail with `ImportError`. The alias `DelegationToolset = AgentToolset` is in `agent_toolset.py`, but the old module is gone. Should add a compatibility shim at the old path.

## 5. Inconsistency: Delegation Check Uses Different Config Path

**File:** `llm_do/runtime.py:168-170` vs `llm_do/agent_toolset.py:74-76`

Runtime checks:
```python
delegation_config = toolsets.get("delegation", {})
allowed = delegation_config.get("allow_workers", [])
```

But AgentToolset receives config directly:
```python
return self._config.get("allow_workers", [])
```

The toolset loader must pass the inner config dict, but this isn't obvious and could cause bugs if the wrapper structure changes.

## 6. Feature Gap: Agent Tools Don't Support Attachments

**File:** `llm_do/agent_toolset.py:354-360`

The `_agent_*` tools only accept `input: str`, while `worker_call` supports `attachments`. The `_prepare_attachments` method is only used by `worker_call`. If attachments are needed, users must fall back to the old pattern.

## 7. Overengineering: `cost_tracker` Placeholder

**File:** `llm_do/types.py:289-291, 330`

```python
cost_tracker: Optional[Any] = None  # Future enhancement: track costs across nested calls
```

Adds field with no implementation. Consider deferring until actually implemented.

## 8. Documentation Mismatch

**File:** `llm_do/agent_toolset.py:10-11`

Docstring says tools are named `summarizer(input=...)` but actual implementation uses `_agent_summarizer(input=...)`. The prefix is correct behavior but docs are wrong.

## Summary

| Severity | Issue |
|----------|-------|
| **High** | `worker_call` bypasses `allow_workers` validation |
| **Medium** | Import path `llm_do.delegation_toolset` broken |
| **Medium** | Broad exception catch hides real errors |
| **Low** | Unused `_worker_descriptions` cache |
| **Low** | Agent tools lack attachment support |
| **Low** | Placeholder `cost_tracker` field |
| **Low** | Minor docstring inaccuracy |
