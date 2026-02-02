# Useless Features Audit - 2026-01-24

**Date:** 2026-01-24
**Status:** Complete
**Type:** Periodic audit

## Summary

This audit reviews the codebase for features that add complexity without clear value, following the periodic audit schedule. The codebase has undergone significant refactoring since the last audit (2026-01-13), with the Worker class removed and replaced by AgentSpec/EntrySpec architecture. A follow-up pass on the same date found additional unused API surface (usage/message_log collectors, EntrySpec.description, AgentRegistry helpers, Runtime.run) and confirmed the earlier ToolsetFactory context concern is already resolved.

## Status of Previous Recommendations

| Feature | Previous Status | Current Status | Action |
|---------|-----------------|----------------|--------|
| `output_model` | Remove (deferred) | **Still present on AgentSpec** | Remove |
| `cache_key_fn` | Remove | **Removed** | None |
| `model_settings` | Keep for programmatic use | **Still present on AgentSpec** | Keep |
| `toolset.id` | Keep (documented) | Present | None |

## Current Findings

### 1. `output_model` on AgentSpec - **REMOVE**

**Location:** `llm_do/runtime/contracts.py:82`

**Current state:**
- Field exists on the new `AgentSpec` class (line 82)
- Validation exists in `__post_init__` (lines 89-90)
- Used in `agent_runner.py:100`: `output_type=spec.output_model or str`
- **No code anywhere sets `output_model=` to a non-None value**
- Grep search: `output_model=` returns 0 matches in source code

**Evidence:**
```python
# contracts.py:82
output_model: type[BaseModel] | None = None

# agent_runner.py:100 - only usage
output_type=spec.output_model or str,
```

**Recommendation:** Remove. This field has survived three audits (initial + two follow-ups) and remains unimplemented. The validation code (lines 89-90) suggests it was meant to work like `input_model`, but no parsing or configuration mechanism exists.

---

### 2. `model_settings` on AgentSpec - **KEEP**

**Location:** `llm_do/runtime/contracts.py:83`

**Current state:**
- Field exists on `AgentSpec`
- Passed through to PydanticAI `agent.run()` in agent_runner.py (lines 182, 234)
- Cannot be set from worker files (no parsing support)
- Could be useful for programmatic agent construction

**Recommendation:** Keep. Unlike `output_model`, this field has a working implementation path - it's passed to PydanticAI and would work if set. It's available for programmatic use.

---

### 3. Runtime usage collection (`UsageCollector`, `Runtime._create_usage`, `Runtime.usage`) - **REMOVE OR WIRE**

**Location:** `llm_do/runtime/runtime.py:20-173`

**Current state:**
- `UsageCollector` stores `RunUsage` objects
- `Runtime._create_usage()` creates a `RunUsage` but has **no call sites**
- `Runtime.usage` has **no call sites** in repo
- The only `RunUsage` usage in tests is direct construction, not via `Runtime`

**Evidence:**
- `rg "_create_usage" llm_do` → only definition in `shared.py`
- `rg "runtime\\.usage" -n` → no matches

**Recommendation:** Either remove the collector entirely (simplest) or wire it into agent runs via `RunContext.usage` so `Runtime.usage` has real data. Right now it is dead API surface and implied state without any data flow.

---

### 4. Runtime message log accumulation + `MessageAccumulator.for_worker` - **CONSIDER REMOVAL / LAZY**

**Location:** `llm_do/runtime/runtime.py:40-176`

**Current state:**
- `Runtime.log_messages()` always appends to `MessageAccumulator`
- `Runtime.message_log` has **no call sites** in repo
- `MessageAccumulator.for_worker()` has **no call sites**
- CLI logging already uses `message_log_callback`; it does not consume `Runtime.message_log`

**Recommendation:** Either remove `MessageAccumulator` entirely or make it opt-in (e.g., only allocate when a caller asks for it). If you want to keep it as a public API, add a small test and document the intended consumer to justify always-on buffering.

---

### 5. `EntrySpec.description` - **REMOVE OR USE**

**Location:** `llm_do/runtime/contracts.py:58`

**Current state:**
- Field exists on `EntrySpec`
- Set when a worker is promoted to entry in `registry.py`
- **Never read** anywhere in runtime/UI/CLI

**Evidence:** `rg "entry_spec\\.description|EntrySpec\\(.*description" -n` → no uses

**Recommendation:** Drop the field unless there is a plan to surface entry descriptions (UI metadata, docs, help output). Right now it's dead metadata.

---

### 6. `AgentRegistry.get()` / `.names()` helpers - **REMOVE OR USE**

**Location:** `llm_do/runtime/registry.py:23-41`

**Current state:**
- Helper methods exist but have **no call sites**
- Runtime stores a raw `dict[str, AgentSpec]` and bypasses `AgentRegistry`
- Most call sites use `.agents` directly

**Recommendation:** Either (a) remove the helpers and make `AgentRegistry` a plain data holder, or (b) update runtime/UI to use `AgentRegistry` so its methods are meaningful. Keeping both adds duplication without behavior.

**Status (2026-01-24):** Removed `.get()`/`.names()`; `AgentRegistry` is now a plain container.

---

### 7. `Runtime.run()` sync wrapper - **CONSIDER REMOVAL**

**Location:** `llm_do/runtime/runtime.py:232`

**Current state:**
- No call sites in code/tests
- Documented in `docs/reference.md`, but untested

**Recommendation:** Remove to reduce API surface, or add a minimal test and keep if sync usage is part of the intended public interface.

---

### 8. Worker Approval Config Tunneling - **CONSIDER SIMPLIFICATION**

**Location:** `llm_do/runtime/runtime.py:66-70`, `llm_do/toolsets/agent.py:68-72`

**Current state:**
Three related fields in RuntimeConfig:
- `worker_calls_require_approval`
- `worker_attachments_require_approval`
- `worker_approval_overrides`

These are:
- Passed through 5+ layers of function signatures
- Only consumed in `AgentToolset.needs_approval()` via defensive `getattr()` calls

**Recommendation:** Consider moving these to AgentToolset construction context rather than RuntimeConfig. Not a "useless feature" but parameter tunneling anti-pattern.

---

## Architecture Changes Since Last Audit

The codebase underwent significant refactoring:

1. **Worker class removed** - Replaced with `AgentSpec` + `EntrySpec` architecture
2. **EntryFunction removed** - Replaced with `EntrySpec` (simpler dataclass)
3. **CallContext simplified** - Now a thinner protocol implementation

These changes align with the audit's goal of reducing unnecessary complexity.

---

## Checklist Status

From `tasks/recurring/find-useless-features.md`:

### Core Classes
- [x] **Worker class** - Removed, replaced by AgentSpec
- [x] **Runtime class** - Reviewed, approval tunneling noted
- [x] **EntryFunction** - Removed, replaced by EntrySpec
- [x] **Toolset wrapper** - Removed; replaced by ToolsetDef + TOOLSETS registry factories

### Dead Code
- [x] Functions/methods with no callers - `Runtime._create_usage`, `Runtime.usage`, `Runtime.message_log`, `MessageAccumulator.for_worker`, `AgentRegistry.get`, `AgentRegistry.names`, `Runtime.run`
- [x] Conditionals that always evaluate same way - None found
- [x] Parameters never overridden - `output_model` never set; `EntrySpec.description` never read

### Configuration/Registry
- [x] `RunApprovalPolicy` - Clean after `cache_key_fn` removal
- [x] Toolset approval config - Working, minor tunneling issue

### Recent Additions (since 2026-01-13)
- [x] AgentSpec/EntrySpec refactor - Clean, well-motivated
- [x] CallScope changes - Reviewed, no issues

---

## Recommendations

### Immediate Action

1. **Remove `output_model`** from `AgentSpec`
   - Delete field from `llm_do/runtime/contracts.py:82`
   - Delete validation from `llm_do/runtime/contracts.py:89-90`
   - Update `llm_do/runtime/agent_runner.py:100` to always use `str` output type
2. **Remove or wire `Runtime.usage`**
   - If no immediate plan to plumb usage into `Agent.run`, delete `UsageCollector`, `_create_usage()`, and `Runtime.usage`
   - Otherwise, add a wiring path so usage is actually collected
3. **Decide on `EntrySpec.description`**
   - Remove if unused, or surface it somewhere (UI/CLI metadata)

### Consider for Future

1. **Message log buffering** - Make `Runtime.message_log` opt-in or remove if unused
2. **AgentRegistry helpers** - Removed (2026-01-24)
3. **Runtime.run()** - Remove or add a small test + doc call site
4. **Approval config location** - Could move worker approval settings closer to AgentToolset

---

## Impact Assessment

Removing `output_model` would:
- Remove 4 lines of dead code
- Remove untested validation path
- Clarify actual API surface vs aspirational features
- Not break any existing code (field is never set)

Removing `UsageCollector` / `Runtime.usage` would:
- Delete dead plumbing with no consumers
- Reduce memory overhead and API surface
- Force a clearer decision about how (or whether) usage data should be exposed

---

## Notes

- The Worker class refactor (commits since 2026-01-13) addressed many complexity concerns
- `output_model` has persisted through three audits - time to remove it
- The codebase is cleaner than the last audit due to architectural simplification
- ToolsetFactory context parameter is already removed; earlier concern is now resolved
