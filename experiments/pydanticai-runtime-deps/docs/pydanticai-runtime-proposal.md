# Proposal: Run-Scoped Policy for Agent Delegation in PydanticAI

Status: draft (not submitted)
Author: llm-do experiment notes
Context: experiments/pydanticai-runtime-deps

## Summary
PydanticAI already supports "agent delegation" by calling another agent inside a tool. This is powerful, but it lacks a
standard place to enforce cross-cutting policy (delegation depth limits, approvals, unified event logging). In llm-do we
model these as a small runtime object passed to workers. This proposal suggests a minimal, non-breaking way to make such
policy first-class in PydanticAI without introducing global singletons or large architectural changes.

The core idea: allow a **per-run policy object** (or protocol) to be attached to the run and surfaced in the `RunContext`
so that "agent as tool" delegation can read and update it (e.g., increment depth) in a consistent way.

## Background
In the experiments here, a tiny `AgentRuntime` object stored in `deps` provides:
- Agent registry for delegation
- Depth tracking (`max_depth`)
- Usage aggregation via `usage=ctx.usage`
- Attachment resolution (`BinaryContent` from file paths)
- Optional event logging (via `event_stream_handler`)

This works, but it is **not first-class**: it depends on app conventions rather than PydanticAI semantics. The missing
piece is a standard hook or object that PydanticAI recognizes as the **run policy**.

## Problem
Delegation by wrapping an agent inside a tool function has a few rough edges:
- **Depth**: no built-in mechanism to increment or enforce depth across delegated agent runs.
- **Approvals**: approvals require tool wrappers; policy is not centralized at the run level.
- **Event logging**: logging across delegated runs requires manual propagation.
- **Ergonomics**: every app must reinvent the same "runtime" pattern.

We can solve this in user code, but the duplication is substantial and the pattern is stable enough to warrant a small
upstream abstraction.

## Design Goals
- Small, additive API change.
- Avoid global state; must be per-run and safe for concurrent runs.
- Enable depth accounting across agent delegation.
- Make approval policy pluggable without rewriting tool logic.
- Maintain current PydanticAI mental model: Agent, tool, RunContext.

## Non-Goals
- Do not introduce a new orchestration engine or replace the agent loop.
- Do not change the existing `deps` semantics.
- Do not require any new global registry or singleton.

## Proposal: Run Policy (Option A)
Add an optional `run_policy` (or `runtime`) argument to `Agent.run` / `run_sync`, stored on `RunContext` and propagated to
delegated runs.

### API Sketch
```python
class RunPolicy(Protocol):
    def spawn(self) -> "RunPolicy": ...
    def on_delegation(self, agent_name: str) -> None: ...

@dataclass
class DepthPolicy:
    max_depth: int
    depth: int = 0

    def spawn(self) -> "DepthPolicy":
        if self.depth >= self.max_depth:
            raise RuntimeError("max_depth exceeded")
        return replace(self, depth=self.depth + 1)

result = agent.run(
    "prompt",
    run_policy=DepthPolicy(max_depth=5),
)
```

`RunContext` would gain `run_policy: Any | None`, and delegated runs would use `run_policy.spawn()` by convention.

### Benefits
- Clear, explicit surface for policy.
- Works with concurrent runs (no globals).
- Aligns with existing `RunContext` patterns (usage, metadata).

### Trade-offs
- Adds a new concept to the API.
- Requires a small amount of plumbing in the agent loop and context.

## Proposal: Agent-as-Tool Helper (Option B)
Add a helper that wraps an agent as a tool and centralizes depth handling:

```python
tool = agent.as_tool(
    name="delegate",
    run_policy=policy,
    usage=ctx.usage,
)
```

### Benefits
- Very small surface change.
- Solves depth for the most common delegation path.

### Trade-offs
- Only applies to agent-as-tool patterns.
- Less general than a run-scoped policy object.

## Proposal: Delegation Hook (Option C)
Add a hook invoked before/after delegated runs:

```python
agent.run(prompt, on_delegation=hook)
```

### Benefits
- Minimal invasive change.

### Trade-offs
- Less explicit than a policy object.
- Easy to under-specify; may not scale to approvals or other policies.

## Recommendation
Start with **Option A (run policy)** plus a small helper for Option B:
- `run_policy` is general and can cover approvals, depth, rate limiting, logging.
- `agent.as_tool()` can be a convenience wrapper that uses `run_policy.spawn()`.

This keeps PydanticAI's model intact while giving a formal place for applications to implement policy once.

## Approvals Considerations
Approvals are currently handled by wrapping tool calls or by relying on toolset-specific mechanisms. A `run_policy` object
could supply a `deferred_tool_handler` or approval callback used by the core tool execution loop. This keeps policy
centralized and avoids duplicating approval logic per tool.

## Example: Depth + Approvals Together
```python
@dataclass
class AppPolicy:
    depth: int
    max_depth: int
    approvals: ApprovalHandler

    def spawn(self) -> "AppPolicy":
        if self.depth >= self.max_depth:
            raise RuntimeError("max_depth exceeded")
        return replace(self, depth=self.depth + 1)

    async def handle_tool(self, ctx, tool_call):
        return await self.approvals(ctx, tool_call)
```

## Compatibility
- Fully backward-compatible; `run_policy` is optional.
- No behavior changes if `run_policy` is unset.

## Open Questions
- Naming: `run_policy`, `runtime`, or `run_state`?
- Should `RunContext` expose `run_policy` directly?
- Should `run_policy.spawn()` be standardized (protocol), or left as convention?
- Should `agent.as_tool()` accept a `run_policy` argument?

## Rationale for Avoiding Singletons
A global runtime object does not work for concurrent runs, multi-user environments, or tests. Run-level policy must be
instantiated per run and passed explicitly (or per-agent default), which is consistent with PydanticAI's current design.

## References
- Experiment: `experiments/pydanticai-runtime-deps/` in this repo
- PydanticAI docs: agent delegation + event streaming (local clone)
