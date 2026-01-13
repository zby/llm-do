# Useless Features Audit

**Date:** 2026-01-13
**Status:** Complete

## Summary

This audit reviewed the codebase for features that add complexity without clear value, similar to the removed `bulk_approve_toolsets` feature. The focus was on optional parameters, dead code paths, and features that exist but lack practical usage.

## Candidates for Action

| Feature | Location | Concern | Decision |
|---------|----------|---------|----------|
| `schema_out` | Worker class | Partially implemented - no file parsing | **Remove** |
| `model_settings` | Worker class | Cannot set from worker files | **Investigate** |
| `cache_key_fn` | RunApprovalPolicy | Never customized | **Remove** |
| `toolset.id` | All toolsets | Implemented but never consumed | **Keep (documented)** |

## Detailed Findings

### 1. `schema_out` on Worker - **RECOMMEND REMOVAL**

**What it is:** Optional field to specify output type validation for Worker responses.

**Evidence of disuse:**
- Field exists on Worker (`llm_do/runtime/worker.py:404`)
- Used when building agent (`output_type=self.schema_out or str`)
- **No `schema_out_ref` parsing in worker files** - unlike `schema_in_ref` which is parsed
- No tests verify this functionality
- Not used in any examples
- Only mentioned in old design notes as a future feature

**Code paths:**
```python
# worker.py:404
schema_out: Optional[Type[BaseModel]] = None

# worker.py:433 - only usage
output_type=self.schema_out or str,
```

**Recommendation:** Remove `schema_out` from Worker. If output validation is needed in the future, implement it properly with `schema_out_ref` parsing and tests.

---

### 2. `model_settings` on Worker - **INVESTIGATE FURTHER**

**What it is:** PydanticAI ModelSettings for configuring model behavior (temperature, etc.).

**Evidence of limited use:**
- Cannot be set from worker files (no parsing support)
- Only one test (`test_wrap_toolsets_preserves_worker_fields`) verifies field preservation
- Not used in any examples
- Used in OAuth module for API headers (different purpose)

**Code paths:**
```python
# worker.py:402
model_settings: Optional[ModelSettings] = None

# worker.py:602, 654 - passed to agent.run()
model_settings=self.model_settings,
```

**Recommendation:** Either:
1. Remove if programmatic Worker construction is not a priority use case
2. Or add `model_settings` parsing to worker files if there's demand

---

### 3. `cache_key_fn` on RunApprovalPolicy - **RECOMMEND REMOVAL**

**What it is:** Optional function to customize approval cache key generation.

**Evidence of disuse:**
- Never passed as a custom value in any code
- Always falls back to `_default_cache_key`
- The `cache` parameter itself IS used (in CLI)
- No tests for custom cache key functions

**Code paths:**
```python
# approval.py:33
cache_key_fn: Callable[[ApprovalRequest], Any] | None = None

# approval.py:203 - always uses default
cache_key_fn=policy.cache_key_fn or _default_cache_key,
```

**Recommendation:** Remove `cache_key_fn` parameter. The default implementation is sufficient and customization adds API surface without demonstrated need.

---

### 4. `toolset.id` property - **KEEP (but document intent)**

**What it is:** Property on all toolsets returning an optional identifier.

**Status:**
- Implemented on FileSystemToolset, ShellToolset, AttachmentToolset, WorkerToolset, ApprovalDeniedResultToolset
- Comments reference "durable execution" integration
- **Never consumed by any code in llm-do**

**Code pattern:**
```python
@property
def id(self) -> str | None:
    """Return toolset ID for durable execution."""
    return self._id
```

**Recommendation:** Keep, but clarify in docstrings that this is for external integration (Temporal/Prefect). The feature is intentionally available for future/external use, not dead code.

---

## Features Verified as Used

These features were audited and confirmed to have proper usage:

| Feature | Status | Evidence |
|---------|--------|----------|
| `schema_in` | **Active** | 50+ uses across tests, examples, core code |
| `compatible_models` | **Active** | Extensive test coverage, used for model validation |
| `base_path` | **Active** | Used in examples for attachment path resolution |
| `builtin_tools` | **Active** | Used for server_side_tools (web_search) |
| `description` | **Active** | Parsed from worker files, used in tool definitions |
| `verbosity` | **Active** | Controls streaming output, well-tested |
| `server_side_tools` | **Active** | Used in examples and has test coverage |
| `return_permission_errors` | **Active** | Used in TUI mode for graceful denials |
| `message_log_callback` | **Active** | Used in CLI for verbose output |
| `cache` on RunApprovalPolicy | **Active** | Used in CLI for session caching |
| `allow_cli_input` | **Active** | Used in CLI input validation |
| `entry.input` | **Active** | Used for manifest-based input |

## Recommendations

### Immediate Actions

1. **Remove `schema_out`** - It's half-implemented and creates false expectations
2. **Remove `cache_key_fn`** - Unnecessary customization point

### Consider for Future

1. **`model_settings`** - Decide on the supported configuration surface
   - If programmatic-only: keep as-is
   - If worker files should support it: add parsing
   - If neither: remove

### Documentation

1. **`toolset.id`** - Add explicit note that this is for external workflow engine integration, not internal use

## Impact Assessment

Removing the recommended features would:
- Reduce cognitive load when reading Worker/RunApprovalPolicy classes
- Remove untested code paths
- Clarify the actual feature set vs. aspirational features
- Not break any existing user code (features are unused)

## Notes

- The `bulk_approve_toolsets` removal (c50ad64) that inspired this audit was a good example of removing complexity without clear value
- The `schema_out_ref` pattern in `docs/notes/recursive-problem-patterns.md` suggests this was planned but never implemented
- Focus should be on features with demonstrated demand, not speculative API surface
