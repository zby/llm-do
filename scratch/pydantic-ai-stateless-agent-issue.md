# Issue: Agent "stateless and global" claim needs toolset state caveat

## The documented claim

Two places in the docs state that agents are stateless:

**`docs/agent.md`:**
> **Agents are designed for reuse, like FastAPI Apps**
> You can instantiate one agent and use it globally throughout your application, as you would a small FastAPI app or an APIRouter

**`docs/multi-agent-applications.md`:**
> Since agents are **stateless and designed to be global**, you do not need to include the agent itself in agent dependencies.

## What's accurate

The Agent itself doesn't accumulate per-run state. Messages are created fresh per run in `GraphAgentState` and returned on `AgentRunResult`. Conversation continuity is explicit via the `message_history` parameter. This part of the claim is correct.

## The gap: toolset state ownership

The Agent holds references to toolsets, and toolsets can carry mutable state. In `Agent._get_toolset()`, per-run toolset preparation handles `DynamicToolset` and static toolsets differently:

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

## `DynamicToolset.copy()` provides shallow isolation only

`DynamicToolset.copy()` clones the wrapper configuration (`toolset_func`, `per_run_step`, `id`) and resets the cached runtime state (`_toolset`, `_run_step`). This ensures the factory function will be called again on the next run. However, the factory function itself is shared by reference — so **isolation depends entirely on what the factory returns**:

```python
def copy(self) -> DynamicToolset[AgentDepsT]:
    """Create a copy of this toolset for use in a new agent run."""
    return DynamicToolset(
        self.toolset_func,       # same factory, shared by reference
        per_run_step=self.per_run_step,
        id=self._id,
    )
```

Three scenarios demonstrate the range of behavior:

```python
class CountingToolset(AbstractToolset):
    def __init__(self):
        self.call_count = 0

    async def call_tool(self, name, tool_args, ctx, tool):
        self.call_count += 1
        return self.call_count

# 1. Static toolset — state bleeds across runs
#    Run 1 sees call_count=1, Run 2 sees call_count=2
agent = Agent('model', toolsets=[CountingToolset()])

# 2. DynamicToolset with fresh-instance factory — properly isolated
#    Run 1 sees call_count=1, Run 2 sees call_count=1
agent = Agent('model', toolsets=[DynamicToolset(lambda ctx: CountingToolset())])

# 3. DynamicToolset with shared-instance factory — state still bleeds
#    Run 1 sees call_count=1, Run 2 sees call_count=2
shared = CountingToolset()
agent = Agent('model', toolsets=[DynamicToolset(lambda ctx: shared)])
```

Case 3 shows that `DynamicToolset` + `copy()` is not sufficient for isolation — it resets the wrapper cache but cannot enforce that the factory produces fresh instances. The isolation guarantee depends on a convention (`toolset_func` should return new instances) that is neither documented nor enforced.

## Why this matters

Users following the documented "stateless and global" pattern will instantiate agents at module level:

```python
agent = Agent(
    'openai:gpt-5',
    toolsets=[MyCustomToolset()],  # static instance
)

# Later, in request handlers:
result1 = await agent.run("query 1")  # MyCustomToolset state persists...
result2 = await agent.run("query 2")  # ...into this run
```

The per-run `async with toolset:` in `Agent.iter()` provides `__aenter__`/`__aexit__` lifecycle hooks, but there's no contract that `__aexit__` must reset all mutable state. It's primarily documented for MCP server cleanup.

### The `DynamicToolset` escape hatch

`DynamicToolset` provides per-run isolation for users who know about it and whose factory returns fresh instances. But:

1. The docs don't caveat the "stateless and global" claim to mention that static toolsets are shared
2. There's no guidance on when to use `DynamicToolset` vs static toolsets for state isolation
3. The `AbstractToolset` base class doesn't document the lifecycle contract — what state should `__aexit__` clean up?
4. `DynamicToolset.copy()` is a shallow wrapper clone, not a deep clone of produced toolset state — the name suggests more isolation than it provides

## Suggested improvements

1. **Caveat the "stateless" claim** in both locations: agents are stateless for messages, but toolsets may carry state. Mention `DynamicToolset` as the mechanism for per-run isolation.

2. **Document the toolset lifecycle contract**: when is `__aenter__`/`__aexit__` called? What's expected of `__aexit__` regarding state cleanup? Is there a difference between the Agent-level enter (reference-counted, for MCP) and the per-run enter (in `Agent.iter()`)?

3. **Document when to use `DynamicToolset`**: if your toolset has mutable state that shouldn't persist between runs, use a `DynamicToolset` factory that returns fresh instances.

4. **Consider clarifying `copy()` semantics**: the current name implies state duplication, but the operation is a shallow wrapper clone that resets cached state. The isolation guarantee depends on an undocumented convention about factory behavior. A clearer name or additional documentation would help.

## Connection to Traits proposal

See [Traits API Research Report](https://github.com/pydantic/pydantic-ai/blob/traits-api-research/traits-research-report.md).

This becomes more significant if/when the Traits API lands. A Trait is a long-lived object on the Agent that provides:
- `get_toolset(ctx: RunContext)` — toolset per run
- `before_tool_call()` / `after_tool_call()` — lifecycle hooks that may accumulate state
- `on_agent_start()` / `on_agent_end()` — per-run hooks

The trait itself persists on the Agent across runs (like static toolsets), but its `get_toolset(ctx)` signature suggests per-run toolset creation. The composition description says "merges toolsets at construction" but `get_toolset` takes a `RunContext` that doesn't exist at construction time.

This is the same static-vs-dynamic tension that exists today with toolsets, but amplified — traits add hooks and guardrails that can also accumulate per-run state on a per-agent-lifetime object. Clarifying the toolset state ownership model now — ideally converging on a consistent factory-based approach with documented conventions — would provide a solid foundation for the traits design.
