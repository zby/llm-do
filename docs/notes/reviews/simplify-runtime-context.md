# Simplify: runtime/context.py

## Context
Review of `CallContext` and agent dispatch helpers.

## Findings
- `call_agent()` manually manages `CallScope` cleanup; use `async with
  CallScope.for_agent(...)` to remove explicit try/finally and centralize
  cleanup behavior.
- Several properties (`agent_registry`, `toolset_registry`, `dynamic_agents`)
  forward directly to `runtime`. If only used in a few places, consider
  accessing `runtime` directly to reduce the CallContext surface.
- `_resolve_agent_spec()` duplicates lookup logic that could live on
  `AgentRegistry` or a shared helper, reducing one-off lookup code.

## Open Questions
- Is the CallContext API meant to be minimal (config + frame), or do we
  intentionally expose registries for convenience?

## 2026-02-09 Review
- `CallContext` still exposes multiple runtime pass-through properties (`agent_registry`, `tool_registry`, `toolset_registry`, `dynamic_agents`), expanding surface area without adding logic.
- `_resolve_agent_spec()` remains local lookup/formatting logic that could live on `AgentRegistry` for reuse.
- `call_agent()` now uses `async with CallScope.for_agent(...)` cleanly; remaining simplification is mostly API surface reduction.
