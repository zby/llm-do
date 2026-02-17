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

The Agent holds references to toolsets, and toolsets can carry mutable state. In `Agent._get_toolset()` (agent/__init__.py:1551-1557), per-run toolset preparation handles `DynamicToolset` and static toolsets differently:

```python
def copy_dynamic_toolsets(toolset):
    if isinstance(toolset, DynamicToolset):
        return toolset.copy()
    else:
        return toolset  # same instance, shared across runs
```

This means:
- **`DynamicToolset`**: gets a fresh wrapper per run via `copy()`
- **Static `AbstractToolset` instances**: shared across all runs of the same Agent

If a static toolset has mutable internal state (counters, caches, open connections, accumulated context), that state bleeds between runs when the Agent is used "globally" as the docs recommend.

## `DynamicToolset.copy()` is misnamed

The `copy()` method doesn't copy anything. Here's what it does:

```python
def copy(self) -> DynamicToolset[AgentDepsT]:
    """Create a copy of this toolset for use in a new agent run."""
    return DynamicToolset(
        self.toolset_func,       # same factory function, shared by reference
        per_run_step=self.per_run_step,
        id=self._id,
    )
```

It creates a **new `DynamicToolset` wrapper** with `_toolset = None` (reset cache), but the `toolset_func` factory is the same object shared by reference. This isn't a copy — it's a cache invalidation. The name `copy()` suggests state isolation, but the actual operation is "forget the cached toolset so the factory gets called again."

This naming reveals an inconsistency in the design. `DynamicToolset` is already a factory wrapper — the `toolset_func` IS the factory. What `copy()` really does is create a fresh factory invocation point. The method should be called something like `fresh()` or `reset()`, or better yet, shouldn't exist at all — the per-run code should just call the factory directly.

The deeper issue: the codebase has two patterns for toolset freshness, and neither is designed as a coherent lifecycle model:

1. **`DynamicToolset`**: a factory wrapper that caches its output in `_toolset`, with `copy()` to reset the cache. The factory runs lazily on first `get_tools()` call.
2. **Static toolsets**: no freshness mechanism. Same instance forever.

A consistent design would have the Agent always work with factories (or factory-like protocols), producing fresh toolset instances per run. The current two-tier approach — "if you happened to use DynamicToolset you get isolation, otherwise you don't" — is an implicit contract that the "stateless and global" documentation doesn't surface.

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

`DynamicToolset` provides per-run isolation for users who know about it — the factory creates fresh instances per run. But:

1. The docs don't caveat the "stateless and global" claim to mention that static toolsets are shared
2. There's no guidance on when to use `DynamicToolset` vs static toolsets for state isolation
3. The `AbstractToolset` base class doesn't document the lifecycle contract — what state should `__aexit__` clean up?
4. The `copy()` naming suggests deeper isolation than actually provided

## Suggested improvements

1. **Caveat the "stateless" claim** in both locations: agents are stateless for messages, but toolsets may carry state. Mention `DynamicToolset` as the mechanism for per-run isolation.

2. **Document the toolset lifecycle contract**: when is `__aenter__`/`__aexit__` called? What's expected of `__aexit__` regarding state cleanup? Is there a difference between the Agent-level enter (reference-counted, for MCP) and the per-run enter (in `iter()`)?

3. **Document when to use `DynamicToolset`**: if your toolset has mutable state that shouldn't persist between runs, wrap it in a `DynamicToolset` factory.

4. **Consider whether `copy()` should be renamed or removed**: the current name implies state duplication, but the operation is cache invalidation on a factory wrapper. This reflects a design that wasn't fully thought through — the factory pattern is the right idea, but `copy()` grafted onto it obscures the intent.

## Connection to Traits proposal

This becomes more significant if/when the Traits API lands. A Trait is a long-lived object on the Agent that provides:
- `get_toolset(ctx: RunContext)` — toolset per run
- `before_tool_call()` / `after_tool_call()` — lifecycle hooks that may accumulate state
- `on_agent_start()` / `on_agent_end()` — per-run hooks

The trait itself persists on the Agent across runs (like static toolsets), but its `get_toolset(ctx)` signature suggests per-run toolset creation. The composition description says "merges toolsets at construction" but `get_toolset` takes a `RunContext` that doesn't exist at construction time.

This is the same static-vs-dynamic tension that exists today with toolsets, but amplified — traits add hooks and guardrails that can also accumulate per-run state on a per-agent-lifetime object. The inconsistency in the current toolset lifecycle model (factory-via-DynamicToolset vs. static sharing, with `copy()` papering over the gap) will propagate into the traits design if not resolved first.

Clarifying the toolset state ownership model now — ideally converging on a consistent factory-based approach — would provide a solid foundation for traits.
