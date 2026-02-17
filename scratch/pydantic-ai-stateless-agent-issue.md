# Issue: Agent "stateless and global" claim needs toolset state caveat

## The documented claim

Two places in the docs state that agents are stateless:

**`docs/agent.md`:**
> **Agents are designed for reuse, like FastAPI Apps**
> You can instantiate one agent and use it globally throughout your application, as you would a small FastAPI app or an APIRouter

**`docs/multi-agent-applications.md`:**
> Since agents are **stateless and designed to be global**, you do not need to include the agent itself in agent dependencies.

This is accurate for the Agent's own state — messages are created fresh per run in `GraphAgentState` and returned on `AgentRunResult`, with continuity explicit via `message_history`. But the Agent also holds references to toolsets, and toolsets can carry mutable state.

## Observed behavior

`Agent._get_toolset()` handles `DynamicToolset` and static toolsets differently per run:

```python
def copy_dynamic_toolsets(toolset):
    if isinstance(toolset, DynamicToolset):
        return toolset.copy()
    else:
        return toolset  # same instance, shared across runs
```

This creates three distinct behaviors depending on how toolsets are provided:

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

Case 1 is the natural pattern for users following the "stateless and global" guidance. Case 3 shows that even `DynamicToolset` doesn't guarantee isolation — it depends on the factory returning fresh instances, a convention that is neither documented nor enforced.

## The underlying design question

`DynamicToolset` is already a factory wrapper — `toolset_func` IS the factory. `DynamicToolset.copy()` resets the wrapper's cached state (`_toolset`, `_run_step`) so the factory will be called again, but shares the factory function by reference. It's a shallow wrapper clone, not a deep clone of produced toolset state.

This means the factory pattern is the actual mechanism for per-run isolation, but it isn't acknowledged as such in the API. The per-run `async with toolset:` in `Agent.iter()` provides `__aenter__`/`__aexit__` lifecycle hooks, but there's no contract that `__aexit__` must reset mutable state — it's primarily documented for MCP server cleanup.

The result is an implicit two-tier system:
- If you happen to use `DynamicToolset` with a factory that returns fresh instances, you get per-run isolation
- If you use a static toolset (the natural pattern from the docs), you don't

## Suggested improvements

1. **Caveat the "stateless" claim** in both doc locations: agents are stateless for messages, but toolsets may carry state across runs. Point users to `DynamicToolset` for per-run isolation.

2. **Document the toolset lifecycle contract**: when is `__aenter__`/`__aexit__` called? What's expected regarding state cleanup? Clarify the difference between the Agent-level enter (reference-counted, for MCP) and the per-run enter (in `Agent.iter()`).

3. **Document when to use `DynamicToolset`**: if your toolset has mutable state that shouldn't persist between runs, use a `DynamicToolset` factory that returns fresh instances.

4. **Consider making the factory pattern a first-class concept**: if per-run toolset freshness is the intended model for stateful toolsets, the factory pattern deserves explicit API support — a documented protocol for toolset factories, clear guidance on when factories are needed vs. when static instances are safe, and `Agent._get_toolset()` treating factories as the primary path rather than a special case handled via `copy()`.

## Connection to Traits proposal

See [Traits API Research Report](https://github.com/pydantic/pydantic-ai/blob/traits-api-research/traits-research-report.md).

This becomes more significant if/when the Traits API lands. A Trait is a long-lived object on the Agent that provides:
- `get_toolset(ctx: RunContext)` — toolset per run
- `before_tool_call()` / `after_tool_call()` — lifecycle hooks that may accumulate state
- `on_agent_start()` / `on_agent_end()` — per-run hooks

The trait persists on the Agent across runs (like static toolsets), but `get_toolset(ctx: RunContext)` takes a `RunContext`, suggesting per-run evaluation. Meanwhile, the traits composition description says toolsets are "merged at construction" — when no `RunContext` exists yet.

This is the same static-vs-dynamic tension that exists today with toolsets, but amplified: traits add hooks and guardrails that can also accumulate per-run state on a per-agent-lifetime object. Clarifying the toolset state ownership model now — ideally converging on a consistent factory-based approach with documented conventions — would provide a solid foundation for the traits design.
