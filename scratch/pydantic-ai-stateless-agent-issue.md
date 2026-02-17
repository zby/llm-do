# Issue: Agent "stateless and global" claim needs toolset state caveat

## The documented claim

Two places in the docs state that agents are stateless:

**`docs/agent.md:59-60`:**
> **Agents are designed for reuse, like FastAPI Apps**
> You can instantiate one agent and use it globally throughout your application, as you would a small FastAPI app or an APIRouter

**`docs/multi-agent-applications.md:18`:**
> Since agents are **stateless and designed to be global**, you do not need to include the agent itself in agent dependencies.

## What's accurate

The Agent itself doesn't accumulate per-run state. Messages are created fresh per run in `GraphAgentState` and returned on `AgentRunResult`. Conversation continuity is explicit via the `message_history` parameter. This part of the claim is correct.

## The gap: toolset state ownership

The Agent holds references to toolsets, and toolsets can carry mutable state. In `Agent._get_toolset()` (agent/__init__.py:1551-1557), per-run toolset preparation copies `DynamicToolset` instances but passes static `AbstractToolset` instances through unchanged:

```python
def copy_dynamic_toolsets(toolset):
    if isinstance(toolset, DynamicToolset):
        return toolset.copy()  # fresh copy, _toolset reset to None
    else:
        return toolset  # same instance, shared across runs
```

This means:
- **`DynamicToolset`**: correctly isolated per run via `copy()`
- **Static `AbstractToolset` instances**: shared across all runs of the same Agent

If a static toolset has mutable internal state (counters, caches, open connections, accumulated context), that state bleeds between runs when the Agent is used "globally" as the docs recommend.

## Why this matters

Users following the documented pattern will instantiate agents at module level:

```python
agent = Agent(
    'openai:gpt-5',
    toolsets=[MyCustomToolset()],  # static instance
)

# Later, in request handlers:
result1 = await agent.run("query 1")  # MyCustomToolset state persists...
result2 = await agent.run("query 2")  # ...into this run
```

The per-run `async with toolset:` in `iter()` (line 747) provides `__aenter__`/`__aexit__` lifecycle hooks, but there's no contract that `__aexit__` must reset all mutable state. It's primarily documented for MCP server cleanup.

### The `DynamicToolset` escape hatch

`DynamicToolset` solves this for users who know about it — the factory creates fresh instances per run. But:

1. The docs don't caveat the "stateless and global" claim to mention that static toolsets are shared
2. There's no guidance on when to use `DynamicToolset` vs static toolsets for state isolation
3. The `AbstractToolset` base class doesn't document the lifecycle contract — what state should `__aexit__` clean up?

## Suggested improvements

1. **Caveat the "stateless" claim** in both locations: agents are stateless for messages, but toolsets may carry state. Mention `DynamicToolset` as the mechanism for per-run isolation.

2. **Document the toolset lifecycle contract**: when is `__aenter__`/`__aexit__` called? What's expected of `__aexit__` regarding state cleanup? Is there a difference between the Agent-level enter (reference-counted, for MCP) and the per-run enter (in `iter()`)?

3. **Document when to use `DynamicToolset`**: if your toolset has mutable state that shouldn't persist between runs, wrap it in a `DynamicToolset` factory.

## Connection to Traits proposal

This becomes more significant if/when the Traits API lands. A Trait is a long-lived object on the Agent that provides:
- `get_toolset(ctx: RunContext)` — toolset factory per run
- `before_tool_call()` / `after_tool_call()` — lifecycle hooks that may accumulate state
- `on_agent_start()` / `on_agent_end()` — per-run hooks

The trait itself persists on the Agent across runs (like static toolsets), but its `get_toolset(ctx)` signature suggests per-run toolset creation. The composition description says "merges toolsets at construction" but `get_toolset` takes a `RunContext` that doesn't exist at construction time. This is the same static-vs-dynamic tension that exists today with toolsets, but amplified — traits add hooks and guardrails that could also carry per-run state on a per-agent object.

Clarifying the toolset state ownership model now would provide a solid foundation for the traits design.
