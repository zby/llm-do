---
description: Periodic audit of low-value or unused features in runtime/toolset/config surfaces.
---

# Useless Features Audit - 2026-02-09

## Context
Periodic audit for features that add complexity without clear value. Scope: runtime core (`llm_do/runtime/*`), project layer (`llm_do/project/*`), toolsets, models, and configuration surfaces.

## Progress Since Last Audit (2026-01-29)

### Resolved
- **`worker_*` aliases fully removed.** The entire legacy compatibility surface across runtime, manifest, models, args, loader, UI runner, docs, and tests has been eliminated. This was the single largest recommendation from the prior audit and it's been cleanly executed. No traces remain.

### Still Open
Findings 1–4 from the 2026-01-29 audit remain unaddressed.

---

## Findings

### 1) `AgentSpec.output_model` remains dead (carried forward)
**Status:** Unchanged since 2026-01-29.

**Evidence**
- Defined in `llm_do/runtime/contracts.py:120` with validation logic.
- Only consumer: `llm_do/runtime/agent_runner.py:82` as `output_type=spec.output_model or str`.
- No agent file, manifest, or Python-API path sets it. Always `None`, always falls back to `str`.

**Recommendation**
- Remove. The active `tasks/active/schema-composition.md` could reintroduce it with a real `output_model_ref` pipeline when ready.

### 2) `UsageCollector` / `Runtime.usage` / `Runtime._create_usage()` are un-wired (carried forward)
**Status:** Unchanged since 2026-01-29.

**Evidence**
- `UsageCollector` defined at `llm_do/runtime/runtime.py:64`, instantiated at line 199.
- `Runtime._create_usage()` at line 256 — zero call sites.
- `Runtime.usage` property at line 219 — zero call sites.

**Recommendation**
- Remove entirely. Re-add when there's a concrete consumer with defined aggregation semantics.

### 3) `MessageAccumulator` always collects with no reader (carried forward)
**Status:** Unchanged since 2026-01-29.

**Evidence**
- `MessageAccumulator` defined at `llm_do/runtime/runtime.py:81`, instantiated at line 200.
- `Runtime.message_log` property at line 223 — zero call sites in code or tests.
- `Runtime.log_messages()` always appends to the accumulator (unbounded growth), even though the actual consumer is `message_log_callback` which is independently wired.

**Recommendation**
- Remove `MessageAccumulator` and the `Runtime.message_log` property. Keep `message_log_callback` which is the real consumer (used by CLI verbose logging).

### 4) `Runtime.run()` sync wrapper is unused (carried forward)
**Status:** Unchanged since 2026-01-29.

**Evidence**
- `llm_do/runtime/runtime.py:325-349` — zero call sites in code, tests, or examples.
- All callers use `asyncio.run(runtime.run_entry(...))` directly.

**Recommendation**
- Remove, or add a test and document it as a supported convenience method.

### 5) `AgentSpec.model_settings` has no configuration path (new)
**Evidence**
- Defined at `llm_do/runtime/contracts.py:121` with default `None`.
- Consumed in `llm_do/runtime/agent_runner.py:136` where `model_settings = spec.model_settings`.
- Never set via agent files (no `model_settings` frontmatter key) or manifests.
- Only merged with OAuth overrides if OAuth is active — but the base value is always `None`.
- No `model_settings =` assignment found anywhere in the codebase.

**Why it matters**
- Implies configurability that doesn't exist. Only useful as a base for OAuth merging, but starts from `None` in all cases.
- For Python-API consumers who construct `AgentSpec` directly, it's available — but undocumented and untested.

**Recommendation**
- Low priority. Keep for now since Python-API users might set it directly, but note it's untested. Could add a test or remove until agent-file configuration is implemented.

### 6) `_build_agent` has an unused `system_prompt` parameter (new)
**Evidence**
- `llm_do/runtime/agent_runner.py:73`: `system_prompt: str | Sequence[str] | None = None`
- Comment: "intentionally kept for future use (e.g., per-call prompt injection)"
- No caller passes this parameter. Always `None`.

**Why it matters**
- Conflicts with the project's YAGNI policy in `AGENTS.md`.
- Adding unused parameters "for future use" is exactly the pattern YAGNI warns against.

**Recommendation**
- Remove. Re-add when per-call prompt injection is actually implemented.

### 7) `AgentFileParser` class is redundant (new)
**Evidence**
- `llm_do/project/agent_file.py:207-244` — a stateless class wrapping `_extract_frontmatter_and_instructions` and `build_agent_definition`.
- `_default_parser` singleton at line 248 backs the module-level convenience functions `parse_agent_file()` and `load_agent_file()`.
- Only external usage of `AgentFileParser` directly is in tests (`tests/runtime/test_agent_file.py`).
- The class has no state, no configuration, no extension points. Its `parse()` and `load()` methods call the same standalone functions.

**Why it matters**
- An abstraction over two function calls with zero additional behavior.
- Exported in `__init__.py` and documented as public API, increasing surface area for no benefit.

**Recommendation**
- Collapse into module-level functions. Remove the class and the `_default_parser` singleton.

### 8) `select_model()` wrapper is only test-consumed (new)
**Evidence**
- `llm_do/models.py:185-193` — wraps `select_model_with_id()` to return just the `Model`.
- Zero call sites in `llm_do/` production code.
- Called extensively in `tests/test_model_compat.py` (17 call sites).

**Why it matters**
- Low impact; it's a convenience wrapper. But it doubles the public surface for model selection without being used in production.

**Recommendation**
- Low priority. Could be kept as a public convenience, or tests could switch to `select_model_with_id()`.

### 9) `RunApprovalPolicy.cache` is never used (new)
**Evidence**
- `llm_do/runtime/approval.py:29`: `cache: dict[Any, ApprovalDecision] | None = None`
- Passed through in `resolve_approval_callback` at line 156 to `make_tui_approval_callback`.
- No caller of `RunApprovalPolicy()` ever passes `cache=`. Always `None`, always creates a fresh `{}`.

**Why it matters**
- The cache parameter was likely intended for session-level caching persistence, but it's never externally provided.
- The internal `session_cache` in `make_tui_approval_callback` works fine without it.

**Recommendation**
- Low priority. The feature works (the internal dict serves as cache), the parameter just allows external injection. Keep unless simplifying the approval API.

---

## Checklist Status (2026-02-09)

### Core Classes
- [x] **Runtime class** — `output_model`, `UsageCollector`/`usage`, `MessageAccumulator`/`message_log`, `run()` still dead.
- [x] **AgentRegistry** — Clean. No unused fields or methods.
- [x] **CallScope/CallFrame** — Clean. Focused and well-used.
- [x] **CallContext** — Clean. All methods/properties have callers.
- [x] **ToolsetDef** — Clean.

### Dead Code
- [x] `AgentSpec.output_model` (finding 1)
- [x] `UsageCollector`/`Runtime.usage`/`Runtime._create_usage()` (finding 2)
- [x] `MessageAccumulator`/`Runtime.message_log` (finding 3)
- [x] `Runtime.run()` (finding 4)
- [x] `_build_agent` `system_prompt` parameter (finding 6)

### Test Coverage Patterns
- [x] `select_model()` — tested but unused in production (finding 8)
- [x] `AgentFileParser` — tested but redundant over module functions (finding 7)

### Configuration/Registry
- [x] `RunApprovalPolicy` — all modes used; `cache` parameter unused externally (finding 9)
- [x] `AgentSpec.model_settings` — field exists but no configuration path (finding 5)
- [x] Approval config — all options wired through manifest → CLI → Runtime.

### Recent Additions
- [x] No new speculative features observed since last audit.

---

## Summary

The codebase is leaner since the `worker_*` removal. The remaining dead features are the same ones flagged on 2026-01-29 (findings 1–4), plus three new ones:
- A YAGNI `system_prompt` parameter (finding 6)
- A redundant `AgentFileParser` class (finding 7)
- An un-wired `model_settings` field (finding 5)

**Highest-value removals** (ordered by complexity reduction):
1. `UsageCollector` + `Runtime.usage` + `_create_usage()` — dead infrastructure
2. `MessageAccumulator` + `Runtime.message_log` — unbounded accumulation with no reader
3. `AgentSpec.output_model` — half-implemented feature
4. `Runtime.run()` — untested sync wrapper
5. `_build_agent` `system_prompt` parameter — YAGNI violation
