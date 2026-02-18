---
description: PydanticAI should handle the common lifecycle cases cleanly (stateless, shared, per-run fresh) and provide explicit extension points for exotic ones (snapshot, transactional, inherited) rather than trying to model all policies
areas: []
status: current
---

# Proposed toolset lifecycle resolution for PydanticAI

## The constraint

[[toolset-state-spectrum-from-stateless-to-transactional]] identifies at least five distinct lifecycle policies for toolsets: global singleton, per-run fresh, per-agent-call fresh, snapshot from parent, and inherited from parent. PydanticAI cannot and should not try to model all of these — the exotic combinations (snapshot semantics, shared transactions, per-field isolation) are domain-specific and fundamentally depend on the relationship between caller and callee.

But PydanticAI should handle the common cases well and leave clear extension points for the rest. The current design handles global singletons (static toolsets) and has a mechanism for per-run freshness (`DynamicToolset`), but neither is documented as a lifecycle model. The gap isn't in capability — it's in explicitness.

## Proposal: three layers

### Layer 1: Document what exists (minimal effort, high value)

The existing mechanisms already cover the two most common non-stateless cases. They just need documentation:

**Static toolsets = global singleton lifecycle.** When you pass an `AbstractToolset` instance to `Agent(toolsets=[...])`, that instance is shared across all runs. This is correct for MCP servers, connection pools, and stateless toolsets. Document that this is the intended behavior, not an accident.

**`DynamicToolset` = per-run fresh lifecycle.** When you wrap a factory in `DynamicToolset`, a fresh toolset instance is created per run. This is correct for caches, counters, browser sessions, and anything with per-conversation state. Document when to use it, and document that isolation depends on the factory returning fresh instances.

**`__aenter__`/`__aexit__` lifecycle contract.** Currently underdocumented. Clarify:
- Agent-level enter/exit: for long-lived resources (MCP server processes). Reference-counted. Called once per Agent context.
- Per-run enter/exit: called within `Agent.iter()` for each run. DynamicToolset uses this to create and clean up its inner toolset.
- What `__aexit__` should do: release resources acquired in `__aenter__`. NOT expected to reset all mutable state — that's the factory's job.

This layer is purely documentation. No code changes needed.

### Layer 2: Make the factory pattern first-class (moderate effort)

`DynamicToolset` is the right idea but the API is indirect. The developer has to know to wrap their factory in `DynamicToolset`, and `copy()` obscures what's actually happening. Two options:

**Option A: Sugar on Agent construction.** Accept factories directly in `toolsets=`:

```python
# Current — requires knowing about DynamicToolset
agent = Agent('model', toolsets=[DynamicToolset(lambda ctx: BrowserToolset())])

# Proposed — factory detected automatically
agent = Agent('model', toolsets=[lambda ctx: BrowserToolset()])
```

PydanticAI already accepts callables for `@agent.tool` — extending this to toolsets would be consistent. Internally, wrap in `DynamicToolset`. This is a small quality-of-life change that makes the factory pattern visible at the call site.

**Option B: Class-level lifecycle declaration.** Let the toolset class declare its preferred lifecycle:

```python
class BrowserToolset(AbstractToolset):
    per_run = True  # framework should create fresh instances per run

    @classmethod
    def create(cls, **config) -> 'BrowserToolset':
        return cls(**config)
```

The Agent inspects `per_run` and auto-wraps in a factory using `create()`. This is more structured but risks becoming a leaky abstraction — the toolset author declares intent, the framework enforces it, but the agent author can't easily override.

**Recommendation:** Option A is simpler and more aligned with Python conventions. The factory is explicit at the composition site. Option B encodes a default in the toolset class, which is useful but can be added later on top of Option A.

### Layer 3: Extension points for sub-agent isolation (design investment)

This is where the exotic cases live: snapshot semantics, shared transactions, inherited state. PydanticAI shouldn't model these directly, but should provide hooks for libraries (like llm-do) and developers to implement them.

**The minimal extension point: a toolset-for-sub-agent hook.** When an agent delegates to a sub-agent, the framework needs to decide which toolsets the sub-agent gets. Currently there are two options: same instance (shared) or completely independent (via factory). The missing middle ground is a hook that lets the developer control this per-delegation:

```python
class AbstractToolset:
    def for_sub_agent(self) -> 'AbstractToolset':
        """Return a toolset instance for a sub-agent.

        Default: return self (shared).
        Override for isolation or snapshot semantics.
        """
        return self
```

This is essentially `isolated_copy()` from external analysis, but named to communicate its purpose: produce a toolset appropriate for a sub-agent. The toolset author encodes domain knowledge:

- `BrowserToolset.for_sub_agent()` → new instance with parent's URL, reset scroll
- `TransactionalToolset.for_sub_agent()` → `self` (share the transaction) or new instance from the pool (isolate)
- `CachingSearchToolset.for_sub_agent()` → `self` (share the cache warmth)
- `FileSystemToolset.for_sub_agent()` → depends on toolset config (shared cwd vs isolated)

The default (`return self`) is correct for the common cases: stateless toolsets, shared resources, and toolsets that don't care about sub-agent isolation. Only toolsets with per-run state need to override.

**The override at composition time.** The toolset's `for_sub_agent()` provides the default, but the agent author should be able to override it at wiring time:

```python
# Use the toolset's default isolation behavior
sub_agent = Agent(toolsets=[browser_toolset])

# Override: force fresh instance regardless of toolset default
sub_agent = Agent(toolsets=[lambda ctx: BrowserToolset()])

# Override: force sharing regardless of toolset default
sub_agent = Agent(toolsets=[browser_toolset])  # pass same instance
```

This is already how it works today with the factory pattern. `for_sub_agent()` just adds a middle option: "let the toolset decide" rather than forcing the agent author to choose between raw instance (shared) and factory (fresh).

**What this doesn't handle** — and shouldn't:

- Distributed transactions across parallel sub-agents — this is infrastructure, not framework
- Automatic rollback on sub-agent failure — this requires transaction boundary management that belongs in the harness, not the toolset protocol
- Per-field snapshot decisions — these are encoded in `for_sub_agent()` implementations, not in the framework

## What this means for Traits

If PydanticAI adopts these layers, traits ([#4303](https://github.com/pydantic/pydantic-ai/issues/4303)) would have a clear model to build on:

- **Layer 1** gives traits a documented lifecycle contract for their toolsets
- **Layer 2** means `Trait.get_toolset(ctx)` has a clear interpretation: it's a factory call, evaluated per-run, producing a fresh toolset. The trait object is long-lived; the toolset it provides is per-run.
- **Layer 3** means traits that provide stateful toolsets (browser, REPL) can implement `for_sub_agent()` on their toolsets, giving sub-agent-aware isolation without the traits system needing to model it explicitly

The tension in the traits proposal — `get_toolset(ctx: RunContext)` suggesting per-run evaluation while composition says "merge at construction" — resolves naturally: trait *registration* happens at construction (dependency validation, conflict detection), but toolset *instantiation* happens per-run via the factory pattern. This is exactly the split between `AgentSpec` (static definition) and `CallScope` (per-call instantiation) that llm-do already implements.

## What this means for llm-do

If PydanticAI ships Layer 2 (first-class factory pattern), llm-do's `_per_run_toolset()` wrapper becomes unnecessary — the framework would handle it. If Layer 3 lands (`for_sub_agent()`), llm-do's `CallScope` could use it instead of unconditionally constructing fresh toolsets for sub-agents.

The approval wrapping question remains separate: llm-do wraps toolsets with approval at call time because the approval callback comes from the runtime, not the toolset. This is orthogonal to the lifecycle question and would remain llm-do's responsibility regardless of what PydanticAI ships.

## Open Questions

- Is `for_sub_agent()` the right granularity? It handles the parent→child case but not parallel tool calls within the same agent. Should there be a `for_parallel_call()` as well?
- Should `for_sub_agent()` receive context (which sub-agent, what purpose) or remain context-free? Context-dependent isolation is the FileSystemToolset case — but adding parameters risks overcomplicating the protocol.
- How does this interact with `DynamicToolset`? If a `DynamicToolset`'s inner toolset has `for_sub_agent()`, should the framework call it, or does the factory already handle isolation?

---

Relevant Notes:
- [[toolset-state-spectrum-from-stateless-to-transactional]] — the problem catalog this proposal addresses
- [[toolset-state-prevents-treating-pydanticai-agents-as-global]] — the upstream issue ([pydantic-ai#4347](https://github.com/pydantic/pydantic-ai/issues/4347)) motivating this work

Topics:
- [[index]]
