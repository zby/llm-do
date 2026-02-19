---
description: PydanticAI Traits API (PR #4233) proposes lifecycle hooks and cross-cutting behaviors that could eliminate our approval wrapping and CallScope scaffolding — one of two upstream paths to simplification
areas: [pydanticai-upstream-index, approvals-index]
status: current
pr: https://github.com/pydantic/pydantic-ai/pull/4233
---

# PydanticAI Traits API Analysis

PR [#4233](https://github.com/pydantic/pydantic-ai/pull/4233) is a research report surveying community projects (including llm-do) and proposing a Traits API for PydanticAI v2. Traits are composable, cross-cutting behaviors attached to agents — lifecycle hooks, guardrails, sub-agent patterns, and more. The report catalogs what the community has built on top of PydanticAI and distills common patterns into a proposed framework primitive.

## What Matters for llm-do

The Traits API matters because it's one of two upstream paths that could eliminate our approval wrapping infrastructure. The other is `deferred_tool_handler` (see [we-want-to-get-rid-of-approval-wrapping](./we-want-to-get-rid-of-approval-wrapping.md) for the full comparison). Either path would let us delete ~440 lines of wrapping code and the `pydantic-ai-blocking-approval` dependency.

### Approval wrapping elimination

The proposal includes `before_tool_call` / `after_tool_call` lifecycle hooks on traits. An `ApprovalTrait` implementing `before_tool_call` would intercept every tool call at the agent loop level — no toolset wrapping needed. This is cleaner than `deferred_tool_handler` architecturally (cross-cutting rather than callback-based) but depends on the full Traits API shipping, which is a larger upstream effort.

**Critical requirement:** `before_tool_call` must receive `RunContext[Deps]` so our approval logic can access the callback, session cache, and capability policy. The current proposal signature includes `ctx: RunContext[AgentDepsT]`, which would work.

Our [capability-based-approvals](./capability-based-approvals.md) design pushes further than the report's `ApprovalTrait(mode="writes")` pattern: tools should declare capabilities (`fs.write`, `net.egress`), and a single runtime policy should decide — rather than each trait reimplementing its own approval reasoning.

### CallScope lifecycle replacement

Beyond approvals, traits could subsume our entire `CallScope` / `CallFrame` / `CallContext` stack — per-call isolation, depth tracking, toolset preparation/teardown. This is the largest chunk of PydanticAI impedance-mismatch code we maintain. The proposed `on_agent_start` / `on_agent_end` hooks map directly to what our context managers do today.

### Where we already overlap

The report catalogs patterns llm-do has independently built:

- **Agent-as-tool composition** — our `AgentToolset` is essentially what `SubAgentTrait` describes
- **Name-based registry** — our `Runtime` registries map to the trait catalog's dependency resolution (`requires`, `conflicts_with`)
- **Declarative agent definitions** — our `.agent` files (YAML frontmatter + system prompt) parallel the proposed YAML serialization

## Assessment

`deferred_tool_handler` arrives first and solves the immediate approval wrapping pain. Traits is the better long-term architecture — it eliminates wrapping *and* could replace our lifecycle scaffolding. They're not mutually exclusive: if `deferred_tool_handler` ships first, we migrate to it; when Traits ships later, the delta from handler to trait is small since the wrapping is already gone.

The doc preview for the research report is at https://9956b6bc-pydantic-ai-previews.pydantic.workers.dev/

---

Relevant Notes:
- [we-want-to-get-rid-of-approval-wrapping](./we-want-to-get-rid-of-approval-wrapping.md) — the parent analysis: compares both upstream paths in detail, tracks status and migration requirements
- [capability-based-approvals](./capability-based-approvals.md) — our long-term approval design: tools declare capabilities, runtime decides — pushes further than the report's per-trait approval model
- [proposed-toolset-lifecycle-resolution-for-pydanticai](./proposed-toolset-lifecycle-resolution-for-pydanticai.md) — our three-layer proposal for toolset lifecycle; Traits could subsume Layer 2 (factories) and Layer 3 (extension points)
- [toolset-state-prevents-treating-pydanticai-agents-as-global](./toolset-state-prevents-treating-pydanticai-agents-as-global.md) — the upstream issue Traits would help resolve: per-call Agent construction forced by toolset state

Topics:
- [pydanticai-upstream-index](./pydanticai-upstream-index.md)
- [approvals-index](./approvals-index.md)
