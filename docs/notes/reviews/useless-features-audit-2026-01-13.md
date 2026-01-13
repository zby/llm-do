# Useless Features Audit - Follow-up

**Date:** 2026-01-13
**Status:** Complete
**Type:** Follow-up to initial audit

## Summary

This is a follow-up audit to check whether the recommendations from the initial audit (2026-01-13) have been addressed and to identify any new candidates for removal.

## Status of Previous Recommendations

| Feature | Previous Recommendation | Current Status | Action Needed |
|---------|------------------------|----------------|---------------|
| `schema_out` | Remove | **Still present** | Keep (per user decision) |
| `cache_key_fn` | Remove | **Removed** | None |
| `model_settings` | Investigate | **Still present** | Keep (programmatic use) |
| `toolset.id` | Keep (documented) | Present, documented | None |

## Detailed Status

### 1. `schema_out` on Worker - **REMOVE (unchanged)**

**Location:** `llm_do/runtime/worker.py:404`

**Current state:**
- Field exists but is never set from worker files
- Only internal usage: `output_type=self.schema_out or str` (line 433)
- No `schema_out_ref` parsing exists (unlike `schema_in_ref`)
- No tests verify this functionality
- Not used in any examples

**Code paths:**
```python
# Definition
schema_out: Optional[Type[BaseModel]] = None

# Only usage
output_type=self.schema_out or str,
```

**Recommendation:** Remove. The field is half-implemented and creates false expectations.

---

### 2. `cache_key_fn` on RunApprovalPolicy - **REMOVED**

**Previous location:** `llm_do/runtime/approval.py:33`

**Status:** Removed in this audit.

**Changes made:**
- Removed `cache_key_fn` field from `RunApprovalPolicy` dataclass
- Removed `cache_key_fn` parameter from `make_tui_approval_callback()`
- Updated to use `_default_cache_key()` directly
- All 327 tests pass after removal

---

### 3. `model_settings` on Worker - **DECISION REQUIRED**

**Location:** `llm_do/runtime/worker.py:402`

**Current state:**
- Cannot be set from worker files (no parsing support)
- Only one test (`test_wrap_toolsets_preserves_worker_fields`) verifies field preservation
- Used in OAuth module for HTTP headers (different purpose)
- Used in programmatic Worker construction only
- Passed to PydanticAI agent.run() calls

**Usage pattern:**
```python
# Programmatic construction (experiments, examples)
worker = Worker(
    name="...",
    model_settings=ModelSettings(temperature=0.2),
)
```

**Options:**
1. **Remove** - If programmatic Worker construction is not a priority use case
2. **Keep as-is** - Accept that it's programmatic-only
3. **Add parsing** - Add `model_settings` to worker file frontmatter if there's demand

**Recommendation:** Keep as-is for now. Unlike `schema_out`, this field has a clear use case (programmatic Worker construction) even if it's not settable from worker files.

---

### 4. `toolset.id` Property - **KEEP (documented)**

**Locations:**
- `llm_do/toolsets/filesystem.py:114`
- `llm_do/toolsets/attachments.py:35`
- `llm_do/toolsets/shell/toolset.py:87`
- `llm_do/runtime/worker.py:217`
- `llm_do/runtime/approval.py:75`

**Current state:**
- Implemented on all toolsets
- Only test usage: `assert toolset.id == worker.name` (test_worker_toolset.py:24)
- Never consumed by any production code in llm-do
- Comments reference "durable execution" integration

**Recommendation:** Keep. This is intentionally available for external workflow engine integration (Temporal/Prefect), not dead code.

---

## New Findings

### No New Candidates for Removal

After reviewing:
- Worker class optional fields
- Runtime class configuration options
- EntryFunction optional parameters
- RunApprovalPolicy options
- Dead code patterns (uncalled functions, unused parameters)

All other features are either actively used or intentionally available:

| Feature | Status | Evidence |
|---------|--------|----------|
| `base_path` on Worker | **Active** | Used in examples for attachment path resolution |
| `schema_in` | **Active** | Parsed from worker files, extensive usage |
| `compatible_models` | **Active** | Extensive test coverage, model validation |
| `description` | **Active** | Parsed from worker files, used in tool definitions |
| `server_side_tools` | **Active** | Parsed from worker files, used for web_search etc. |
| `builtin_tools` | **Active** | Used for PydanticAI builtin tools |
| `return_permission_errors` | **Active** | Used in TUI mode for graceful denials |
| `cache` on RunApprovalPolicy | **Active** | Used in CLI for session caching |

---

## Recommendations

### Completed Actions

1. **Removed `cache_key_fn`** from RunApprovalPolicy
   - Deleted field from dataclass
   - Updated `make_tui_approval_callback` to use `_default_cache_key` directly
   - Updated `resolve_approval_callback` to not pass `cache_key_fn`

### Deferred Actions

1. **`schema_out`** - Kept per user decision (may have future use)

### No Action Required

- `model_settings` - Keep for programmatic Worker construction
- `toolset.id` - Keep for external integration

---

## Checklist Status

From `tasks/recurring/find-useless-features.md`:

### Core Classes
- [x] **Worker class** - Reviewed. `schema_out` should be removed.
- [x] **Runtime class** - Reviewed. All options are used.
- [x] **EntryFunction** - Reviewed. All parameters are used.
- [x] **ToolsetSpec** - Reviewed. Simple factory pattern, no unused options.

### Dead Code
- [x] Functions/methods with no callers - None found
- [x] Conditionals that always evaluate the same way - None found
- [x] Parameters with default values never overridden - `cache_key_fn` (should remove)

### Configuration/Registry
- [x] `RunApprovalPolicy` - `cache_key_fn` should be removed
- [x] Toolset approval config - Necessary complexity, working as designed

### Recent Additions
- [x] Reviewed recent commits - No speculative features found
- [x] Per-worker toolset specs (d416358) - Actively used
- [x] Scopes documentation (d463949) - Documentation only

---

## Next Steps

1. Create tasks to implement the removal of `schema_out` and `cache_key_fn`
2. Update recurring task with this audit date
