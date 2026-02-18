---
description: PydanticAI documents agents as stateless and global, but toolsets on agents can carry mutable state across runs — llm-do works around this with per-call Agent construction and toolset factories
areas: []
status: current
---

# Toolset state prevents treating PydanticAI agents as global

## The upstream claim

PydanticAI documents agents as "stateless and designed to be global" (`docs/multi-agent-applications.md`), comparable to FastAPI app objects that you instantiate once and reuse across requests. For the Agent's own state this is accurate — messages are created fresh per run and returned on the result object.

But the Agent holds references to toolsets, and toolsets can carry mutable state: counters, caches, open connections, accumulated context. When a "global" Agent is reused across runs, static toolsets share state between runs.

## How PydanticAI handles it

`Agent._get_toolset()` copies `DynamicToolset` instances per run (resetting the wrapper's cached toolset so the factory runs again) but passes static `AbstractToolset` instances through unchanged. The isolation guarantee for `DynamicToolset` is conditional — it depends on the factory function returning fresh instances, which is a convention that isn't documented or enforced.

This creates an implicit two-tier system: if you use `DynamicToolset` with a well-behaved factory you get per-run isolation; if you use a static toolset (the natural pattern from the docs) you don't.

Filed as a PydanticAI issue — see `scratch/pydantic-ai-stateless-agent-issue.md` for the full writeup with reproduction scenarios.

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

2. **Approval wrapping happens at call time**, not Agent construction — because the approval callback comes from `RuntimeConfig`, which may differ between calls (headless vs TUI vs test).

3. **Per-call Agent construction enables per-call toolset variation** — the same `AgentSpec` can run with different approval policies, different model overrides (OAuth), and at different nesting depths.

4. **`CallScope` owns the lifecycle** — toolset enter/exit, preflight conflict detection, and cleanup are managed per-call, not per-Agent.

## The cost

Per-call Agent construction is wasteful for things that don't change between calls: model resolution, instruction assembly, output schema validation. PydanticAI does this work at Agent construction, so llm-do repeats it every call.

If PydanticAI adopted a first-class factory pattern for toolsets (or separated Agent configuration from toolset binding), llm-do could construct the Agent once and only vary toolsets per-run. But today, `Agent.__init__` takes `toolsets=` and there's no `Agent.run(toolsets=...)` override.

## Connection to Traits proposal

The [Traits API proposal](https://github.com/pydantic/pydantic-ai/blob/traits-api-research/traits-research-report.md) would deepen this tension. Traits are long-lived objects on the Agent that provide toolsets, lifecycle hooks, and guardrails. `Trait.get_toolset(ctx: RunContext)` takes a `RunContext` (suggesting per-run evaluation), but the composition description says traits are merged at Agent construction.

If traits compose at construction and the Agent is long-lived, per-run state on traits faces the same problem as per-run state on static toolsets. If traits compose per-call (as llm-do would need), the dependency validation and topological sorting repeat every call.

The resolution likely requires separating trait *declaration* (static, on the AgentSpec) from trait *activation* (per-run, producing fresh toolsets and binding runtime context). This mirrors what llm-do already does with `ToolsetDef = AbstractToolset | ToolsetFunc` — the definition is static, the instance is per-call.

## Open Questions

- Should llm-do contribute the factory-based toolset pattern upstream, or wait for traits to force the issue?
- If PydanticAI added `Agent.run(toolsets=...)`, would that eliminate the need for per-call Agent construction?
- How would traits interact with llm-do's approval wrapping — could `ApprovalTrait` receive the callback through `RunContext[deps]`?

---

Relevant Notes:
- [[llm-do-vs-pydanticai-runtime]] — broader comparison of what llm-do adds on top of vanilla PydanticAI, including per-call isolation as a key differentiator

Topics:
- [[index]]
