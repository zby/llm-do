---
description: Periodic audit of low-value or unused features in runtime/toolset/config surfaces.
---

# Useless Features Audit - 2026-01-29

## Context
Periodic audit for features that add complexity without clear value. Scope: runtime core (`llm_do/runtime/*`), toolset specs, registry, manifest/runtime config surfaces, and legacy compatibility aliases.

## Summary
- Unused or un-wired API remains: `AgentSpec.output_model`, `UsageCollector`/`Runtime.usage`, `Runtime.message_log`/`MessageAccumulator`, and `Runtime.run`.
- Legacy `worker_*` aliases persist across runtime, manifest, models, args, loader, UI runner, and docs/tests; this duplicates the `agent_*` surface and conflicts with the "no backcompat" policy.
- No new dead code surfaced beyond prior audit; dynamic agents and `server_side_tools` are exercised in examples/tests.

## Findings

### 1) `AgentSpec.output_model` remains dead (half-implemented)
**Evidence**
- Only referenced in `llm_do/runtime/agent_runner.py` as `output_type=spec.output_model or str`.
- No assignments found in code/tests; `rg -n "output_model" llm_do tests` hits only definitions and that usage.

**Why it matters**
- The field implies output typing is supported but there is no config path for `.agent` or dynamic agents.
- It is a placeholder that increases mental load and suggests a feature that is not actually deliverable today.

**Trade-offs**
- Removing it tightens the API and avoids false affordances.
- Keeping it could support the active `tasks/active/schema-composition.md` work, but only if that work lands soon and includes a real configuration path.

**Recommendation**
- Remove now (YAGNI) and reintroduce alongside schema-composition with a concrete `output_model_ref` pipeline and tests, or explicitly wire it for Python-only AgentSpec creation.

### 2) Usage collection API is un-wired
**Evidence**
- `UsageCollector`, `Runtime._create_usage()`, and `Runtime.usage` have no call sites in `llm_do/` or tests.

**Why it matters**
- Dead API surface suggests telemetry that does not actually exist.
- Thread-safe collection adds complexity and memory without a consumer.

**Trade-offs**
- Wiring usage to PydanticAI would add value but requires clear aggregation semantics (per agent, per run, nested calls) and tests.
- Removing it simplifies the runtime and defers telemetry until needed.

**Recommendation**
- Either wire usage end-to-end (and define a public contract) or remove the collector entirely.

### 3) MessageAccumulator + `Runtime.message_log` are unused and always collecting
**Evidence**
- `Runtime.message_log` has no call sites.
- `MessageAccumulator.for_agent()` is unused.
- `Runtime.log_messages()` always appends to the accumulator, even when no consumer exists.

**Why it matters**
- Unbounded message accumulation for long runs with no reader.
- Duplicates the role of `message_log_callback` (which *is* used in CLI logging).

**Trade-offs**
- Keeping it could be justified if there is a documented programmatic consumer.
- Making it opt-in (lazy allocate on first access or when a flag is set) preserves capability without constant overhead.

**Recommendation**
- Make it opt-in or remove entirely. If kept, document the intended consumer and add tests. Drop `for_agent()` if it remains unused.

### 4) `Runtime.run()` sync wrapper is unused
**Evidence**
- No call sites in code/tests.
- It is not exercised anywhere in examples or CI.

**Why it matters**
- Extra public API surface implies supported behavior that is not validated.

**Trade-offs**
- Keeping a sync entrypoint is convenient but needs tests and explicit docs.
- Removing keeps the API tighter and avoids false guarantees.

**Recommendation**
- Remove or add a minimal test plus doc example to justify it.

### 5) Legacy `worker_*` compatibility surface is still pervasive
**Evidence**
- Aliases and migrations exist in runtime, manifest, models, args, loader, UI runner, and `llm_do/runtime/__init__.py`.
- Docs (`docs/cli.md`) still mention worker-based config fields.
- Tests explicitly cover `worker_*` parameters, which keeps the surface alive.

**Why it matters**
- Doubles the vocabulary and adds adapter logic across many call paths.
- Conflicts with the project policy: "Do not preserve backwards compatibility; prioritize cleaner design."

**Trade-offs**
- Removing will break older API call sites, but the codebase states there are no external consumers.
- Keeping it extends the deprecation tail and increases complexity in perpetuity.

**Recommendation**
- Plan a cleanup sweep to remove all `worker_*` aliases and update tests/docs/examples to use `agent_*` terminology.
- If a brief deprecation window is still desired, mark each alias with `# BACKCOMPAT: <reason> - remove after <condition>` and set a removal date.

## Checklist Status (2026-01-29)
- **Core classes**: Runtime, AgentRegistry, CallScope/CallFrame, CallContext, ToolsetSpec reviewed.
- **Dead code**: `output_model`, `UsageCollector`/`Runtime.usage`, `Runtime.message_log`, `MessageAccumulator.for_agent`, `Runtime.run`.
- **Config/registry**: `worker_*` backcompat remains the largest redundant surface.
- **Recent additions**: No new dead features observed since 2026-01-24.

## Open Questions
- Do we want to drop all `worker_*` aliases immediately, or keep a short, explicit deprecation window?
- Should `output_model` be removed until schema-composition ships, or should we implement `output_model_ref` now?
- If usage/message accumulation stays, what is the exact public contract and who consumes it?

## Conclusion
The runtime is leaner than earlier revisions, but several dead or placeholder features remain. The biggest opportunity is eliminating legacy `worker_*` compatibility and either removing or wiring observability stubs (`UsageCollector`, `message_log`). Removing these would reduce surface area and align the codebase with the stated "no backcompat" policy.
