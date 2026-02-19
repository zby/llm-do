---
description: PydanticAI documents agents as stateless and global, but toolsets on agents can carry mutable state across runs — llm-do works around this with per-call Agent construction and toolset factories
areas: [pydanticai-upstream-index]
status: current
---

# Toolset state prevents treating PydanticAI agents as global

## The upstream claim

PydanticAI documents agents as "stateless and designed to be global" (`docs/multi-agent-applications.md`), comparable to FastAPI app objects that you instantiate once and reuse across requests. For the Agent's own state this is accurate — messages are created fresh per run and returned on the result object.

But the Agent holds references to toolsets, and toolsets can carry mutable state: counters, caches, open connections, accumulated context. When a "global" Agent is reused across runs, static toolsets share state between runs.

## How PydanticAI handles it

`Agent._get_toolset()` copies `DynamicToolset` instances per run (resetting the wrapper's cached toolset so the factory runs again) but passes static `AbstractToolset` instances through unchanged. The isolation guarantee for `DynamicToolset` is conditional — it depends on the factory function returning fresh instances, which is a convention that isn't documented or enforced.

This creates an implicit two-tier system: if you use `DynamicToolset` with a well-behaved factory you get per-run isolation; if you use a static toolset (the natural pattern from the docs) you don't.

Filed as [pydantic-ai#4347](https://github.com/pydantic/pydantic-ai/issues/4347).

## What llm-do does instead

llm-do constructs a **new PydanticAI Agent per call**. The `AgentSpec` is the long-lived definition; the `Agent` is ephemeral:

```
AgentSpec (static, lives in registry)
    │
    │  CallScope.for_agent() — per call
    ▼
_prepare_toolsets_for_run()
    │  wraps each toolset with approval (using current RuntimeConfig)
    │  DynamicToolset factories produce fresh instances
    ▼
_build_agent(spec, runtime, toolsets=wrapped)
    │  new Agent constructed
    ▼
agent.run() → result
    │
Agent discarded
```

Key design choices that follow from this:

1. **All built-in toolsets are factory-wrapped** via `_per_run_toolset(factory)` — no static toolset is ever shared between calls.

2. **Approval wrapping is applied to toolsets before passing them to `Agent(toolsets=...)`** — since PydanticAI binds toolsets at Agent construction, the wrapping must happen before construction.

3. **`CallScope` owns the lifecycle** — toolset enter/exit, preflight conflict detection, and cleanup are managed per-call, not per-Agent.

Note: the approval callback itself doesn't vary between calls — `RuntimeConfig` is frozen and the callback is resolved once at `Runtime.__init__`. Per-call Agent construction is driven by toolset freshness and approval wrapping needing to happen before `Agent(toolsets=...)`, not by per-call policy variation.

## The cost

Per-call Agent construction is a forced choice, not a preference. PydanticAI binds toolsets at `Agent.__init__` and provides no `Agent.run(toolsets=...)` override. Since llm-do needs to wrap toolsets with approval before binding and ensure fresh instances per call, the only option is constructing a new Agent each time. However, [we-want-to-get-rid-of-approval-wrapping](./we-want-to-get-rid-of-approval-wrapping.md) — if either upstream path (deferred_tool_handler or Traits hooks) ships, approval becomes a hook in the agent loop rather than a toolset wrapper, removing the wrapping constraint entirely.

This repeats work that doesn't change between calls: model resolution, instruction assembly, output schema validation. If PydanticAI separated Agent configuration from toolset binding (or adopted a first-class factory pattern for toolsets), llm-do could construct the Agent once and only vary toolsets per-run.

## Connection to Traits proposal

The [Traits API proposal](https://github.com/pydantic/pydantic-ai/blob/traits-api-research/traits-research-report.md) ([issue #4303](https://github.com/pydantic/pydantic-ai/issues/4303)) would deepen this tension. Traits are long-lived objects on the Agent that provide toolsets, lifecycle hooks, and guardrails. `Trait.get_toolset(ctx: RunContext)` takes a `RunContext` (suggesting per-run evaluation), but the composition description says traits are merged at Agent construction.

If traits compose at construction and the Agent is long-lived, per-run state on traits faces the same problem as per-run state on static toolsets. If traits compose per-call (as llm-do would need), the dependency validation and topological sorting repeat every call.

The resolution likely requires separating trait *declaration* (static, on the AgentSpec) from trait *activation* (per-run, producing fresh toolsets and binding runtime context). This is exactly the split llm-do already implements with `ToolsetDef = AbstractToolset | ToolsetFunc` — the definition is static, the instance is per-call. That pattern has been validated in production and could serve as prior art for how PydanticAI resolves the same tension in traits.

## Open Questions

- Should llm-do contribute the factory-based toolset pattern upstream, or wait for traits to force the issue?
- If PydanticAI added `Agent.run(toolsets=...)`, would that eliminate the need for per-call Agent construction?
- How would traits interact with llm-do's approval wrapping — could `ApprovalTrait` receive the callback through `RunContext[deps]`?

---

Relevant Notes:
- [toolset-state-spectrum-from-stateless-to-transactional](./toolset-state-spectrum-from-stateless-to-transactional.md) — comprehensive catalog of toolset state patterns, from pure functions through browser sessions to database transactions
- [llm-do-vs-pydanticai-runtime](./llm-do-vs-pydanticai-runtime.md) — broader comparison of what llm-do adds on top of vanilla PydanticAI, including per-call isolation as a key differentiator
- [we-want-to-get-rid-of-approval-wrapping](./we-want-to-get-rid-of-approval-wrapping.md) — enables: eliminating approval wrapping removes the primary driver of per-call Agent construction

Topics:
- [index](./index.md)
