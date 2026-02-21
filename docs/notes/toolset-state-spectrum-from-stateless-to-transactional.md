---
description: Catalog of toolset state patterns — most tools are stateless so the problem is easy to miss, but shared resources, browser sessions, and DB transactions reveal that toolset lifecycle is an unresolved design question
type: analysis
areas: [pydanticai-upstream-index]
status: current
---

# Toolset state spectrum: from stateless to transactional

Most tools are pure functions — no state, no lifecycle, no problem. This is why [toolset-state-prevents-treating-pydanticai-agents-as-global](./toolset-state-prevents-treating-pydanticai-agents-as-global.md) is easy to miss: the common case works fine with global agents. The problems surface in two distinct ways: **cross-run leakage** (a global agent's static toolset carries state from one run into the next) and **intra-run interference** (parallel calls or sub-agent delegation cause concurrent access to the same stateful toolset). The first is subtle — stale caches, drifting counters — and easy to miss. The second is where state management matters most.

A key insight: the isolation decision isn't purely a property of the toolset — it depends on the **relationship between the caller and the callee**. The same toolset may need sharing in one delegation scenario and isolation in another. This means the framework can't make the decision for you; it can only provide mechanisms for the developer to express their intent at the composition site.

## The spectrum

### 1. Pure functional tools (no state)

```python
@agent.tool
def calculate_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
```

Input in, output out. No side effects, no shared state, no lifecycle. Safe to share across runs, across agents, across parallel calls. This is the vast majority of tools — math, formatting, parsing, validation, lookup.

**Lifecycle need:** None. A global agent with these tools is genuinely stateless.

### 2. Tools with external side effects (stateless toolset, stateful world)

```python
@agent.tool
def write_file(path: str, content: str) -> str:
    Path(path).write_text(content)
    return f"Written to {path}"
```

The toolset itself holds no state, but the tool mutates external state (filesystem, API, database). The toolset is safe to reuse across runs, but the *effects* of one run are visible to the next.

**Lifecycle need:** Minimal for the toolset. But approvals, sandboxing, and undo mechanisms matter at the harness level. This is where llm-do's approval wrapping operates — mediating external effects, not toolset state.

### 3. Shared long-lived resources (MCP servers, connection pools)

```python
mcp_server = MCPServerStdio("npx", ["-y", "@modelcontextprotocol/server-github"])
pool = asyncpg.create_pool(dsn="postgresql://...")

agent = Agent('model', toolsets=[mcp_server, PoolToolset(pool)])
```

The resource is expensive to create and intentionally shared: MCP server processes, database connection pools, HTTP client sessions. Creating a fresh instance per run would be wasteful or impossible (MCP servers need startup time, connection pools need warm connections).

**Lifecycle need:** Shared by design. The Agent-level `__aenter__`/`__aexit__` (reference-counted, for MCP server startup/shutdown) is correct here. Per-run isolation would be counterproductive. PydanticAI handles this case well — it's what the Agent context manager was designed for.

**Complication with sub-agents:** If agent A and agent B both use the same MCP server, they share it naturally. This is usually fine — MCP servers handle concurrent requests. But if the MCP server has per-session state (e.g., a database MCP with a current schema context), sub-agents could interfere with each other.

### 4. Per-run accumulating state (caches, counters, rate limiters)

```python
class CachingSearchToolset(AbstractToolset):
    def __init__(self):
        self.cache: dict[str, str] = {}
        self.call_count = 0

    async def call_tool(self, name, tool_args, ctx, tool):
        self.call_count += 1
        query = tool_args["query"]
        if query not in self.cache:
            self.cache[query] = await web_search(query)
        return self.cache[query]
```

The toolset accumulates state during a run (cache entries, call counts, rate limiter windows). If shared across runs, the cache from run 1 serves stale results in run 2. If the cache is desirable across runs (warm cache), sharing is intentional. If the cache should be fresh per conversation, sharing is a bug.

Note the distinction between "immutable" and "stateless": a toolset backed by a pure function is stateless, but a toolset that caches results from a pure function has state — even if that state is "harmless" in the sense that cache hits and misses don't change observable behavior. Whether that cache should be shared or isolated depends on whether you want the sub-agent to benefit from the parent's cache warmth.

**Lifecycle need:** Depends on intent. This is where the factory pattern matters — `DynamicToolset(lambda ctx: CachingSearchToolset())` gives fresh state per run. But the decision (fresh vs shared) is domain-specific and currently left to the developer with no framework guidance.

**Complication with sub-agents:** If a parent delegates to a sub-agent, should the sub-agent see the parent's cache? For rate limiters, probably yes (shared quota). For search caches, maybe (avoid duplicate searches). For call counters, depends on whether you're tracking per-agent or per-conversation usage. There's no single right answer.

### 5. Stateful sessions (browsers, REPLs, terminal sessions)

```python
class BrowserToolset(AbstractToolset):
    def __init__(self):
        self.browser = None
        self.current_page = None

    async def __aenter__(self):
        self.browser = await playwright.chromium.launch()
        self.current_page = await self.browser.new_page()
        return self

    # Tools: navigate, click, scroll, extract, screenshot
    # Each tool mutates self.current_page state
```

The toolset IS the state. A browser session has a current page, scroll position, cookies, DOM state. A REPL has variables in scope, import state, working directory. A terminal session has cwd, environment variables, running processes.

The tool calls form a sequential conversation with the stateful resource: navigate → scroll → click → extract. The meaning of "scroll down" depends on which page you're on.

**Lifecycle need:** Must be per-run (or per-conversation-segment). Sharing a browser session across independent runs would be nonsensical — the current page from run 1 has nothing to do with run 2.

**Complication with sub-agents — the critical case:** If a main agent is browsing a page and delegates to a sub-agent for analysis, what happens?

- **Same browser session:** The sub-agent can see the page the parent navigated to. But if the sub-agent navigates away (clicks a link, searches for something), the parent returns to a browser on a different page than it left. The parent's mental model (implicit in its conversation history) no longer matches the browser state.
- **Separate browser session:** The sub-agent can't see the parent's page at all. The parent would need to pass the URL or page content explicitly — losing interactive state (scroll position, form inputs, logged-in session).
- **Snapshot (partial copy):** The sub-agent gets a snapshot of the parent's position — current URL and page content — but with reset navigation state (scroll position, form inputs). The sub-agent can read the parent's page or navigate away; either way, the parent's state is unaffected. This is the most nuanced option: it requires per-field decisions about which state to carry over and which to reset. A generic deep clone can't make these distinctions.

This is not hypothetical. Claude Code's sub-agents face this with terminal state: a sub-agent that `cd`s to a different directory could confuse the parent. Claude Code solves this by giving each sub-agent independent execution contexts.

The snapshot option also reveals why a generic deep clone can't solve sub-agent isolation — each field needs a domain-specific decision about whether to carry over or reset. This means isolation logic must live in the toolset implementation, not in a framework-level copy mechanism.

A similar pattern applies to `FileSystemToolset` with a working directory: when a parent delegates to a "search files" sub-agent, they probably want to share the working directory (search where I'm working). When delegating to a "scaffold new project" sub-agent, they want isolation (don't pollute my directory). Same toolset, different isolation needs — the decision depends on the relationship between caller and callee.

### 6. Database transactions

```python
class TransactionalToolset(AbstractToolset):
    def __init__(self, pool):
        self.pool = pool
        self.conn = None
        self.transaction = None

    async def __aenter__(self):
        self.conn = await self.pool.acquire()
        self.transaction = self.conn.transaction()
        await self.transaction.start()
        return self

    async def __aexit__(self, exc_type, *args):
        if exc_type:
            await self.transaction.rollback()
        else:
            await self.transaction.commit()
        await self.pool.release(self.conn)
```

Database transactions present the most complex state management scenario because the correct behavior depends on the semantic intent:

**Same transaction (shared):** A parent agent starts analyzing data and delegates sub-tasks to sub-agents. All agents should see each other's writes — they're collaborating on a single logical operation. The transaction commits or rolls back as a unit.

**Separate transactions (isolated):** A parent agent delegates independent analyses to sub-agents that should not interfere. Each sub-agent works in its own transaction. One sub-agent's failure shouldn't roll back another's work.

**Nested transactions (savepoints):** A sub-agent works within the parent's transaction but can roll back its own changes without affecting the parent. The parent sees the sub-agent's changes only if the sub-agent succeeds. This maps to database savepoints.

**Parallel sub-agents in the same transaction:** Impossible in most databases — a single connection can only run one query at a time. Parallel sub-agents with shared transactional state would need connection-per-agent within a distributed transaction, which is a completely different infrastructure concern.

**The composition-site pattern:** These aren't really different modes of one toolset — they're different toolsets (or the same toolset with different construction-time configuration). The developer picks the semantics at the wiring site:

```python
# Shared transactional context — sub-agent participates in parent's transaction
sub_agent = Agent(toolsets=[tx_toolset])  # same instance

# Independent connections — sub-agent gets its own
sub_agent = Agent(toolsets=[DynamicToolset(lambda ctx: TransactionalToolset(pool))])  # factory
```

The decision lives at the composition site, not inside the toolset. This pattern recurs across the spectrum: the toolset provides a default behavior, and the agent author overrides it at wiring time by choosing between passing the instance (shared) or wrapping in a factory (isolated).

**Lifecycle need:** The transaction lifecycle (begin/commit/rollback) must align with the agent call lifecycle (start/succeed/fail). This means the toolset's `__aenter__`/`__aexit__` must correspond to meaningful transactional boundaries. But PydanticAI's toolset lifecycle doesn't make this correspondence explicit — `__aexit__` might mean "the Agent context closed" or "the run finished" or "the MCP server is shutting down."

### 7. Coordinated multi-resource state

Real applications combine multiple stateful resources:

```python
# An agent that researches a topic, saves findings, and updates a database
agent = Agent('model', toolsets=[
    BrowserToolset(),           # per-run session state
    FileSystemToolset(),        # stateless (external effects only)
    DatabaseToolset(pool),      # shared connection pool
    CachingSearchToolset(),     # per-run cache
])
```

Each toolset has different lifecycle needs. The browser must be per-run. The pool must be shared. The cache could go either way. The filesystem is stateless. There's no single "per-run" or "global" policy that works for all of them.

The coordination challenge goes beyond independent lifecycle policies. Consider an agent that navigates to a form in a browser, fills it with data from a database query, and submits it inside a transaction. If navigation fails mid-way, should the transaction roll back? If the transaction rolls back, should the browser navigate back? These cross-resource consistency questions can't be answered by individual toolset lifecycle policies — they require explicit coordination logic in the harness or application layer.

**Lifecycle need:** Per-toolset lifecycle policies, plus application-level coordination for cross-resource consistency. llm-do's `ToolsetDef = AbstractToolset | ToolsetFunc` enables independent lifecycle choices per toolset, but coordination across toolsets remains the developer's responsibility — and arguably should stay there, since the correct behavior is domain-specific.

## Why the easy cases hide the hard ones

The spectrum explains why PydanticAI's "stateless and global" claim doesn't cause obvious problems for most users:

1. **Most tools are category 1 or 2** — pure functions or external side effects with no toolset state. The global agent pattern works perfectly.

2. **Category 3 (shared resources) works correctly** — MCP servers and pools are designed for sharing. The Agent context manager handles their lifecycle.

3. **Categories 4-7 have two failure modes that surface at different times.** Within a single run, a browser toolset works fine — the state belongs to the conversation. But across runs of a global agent, categories 4-7 leak: the cache from run 1 serves stale results in run 2, the browser session starts on whatever page the last run left. This cross-run leakage is subtle and easy to miss. The more dramatic failures — intra-run interference — only appear with sub-agent delegation or parallel calls.

4. **Most tutorials and examples use stateless tools** — the getting-started path never encounters either failure mode.

The result: developers build intuition on stateless tools, adopt the "global agent" pattern, and only discover cross-run leakage when accumulated state causes a subtle bug. They discover intra-run interference when they add sub-agent delegation or parallel execution. By then the global-agent assumption is baked into the architecture.

## What this means for framework design

The spectrum suggests that toolset lifecycle is not a single concern but at least five distinct policies:

| Policy | When to use | Example | Mechanism today |
|--------|-------------|---------|-----------------|
| **Global singleton** | Expensive shared resource, concurrent-safe | MCP servers, connection pools | Static toolset on Agent |
| **Per-run fresh** | State should not leak between conversations | Browser sessions, caches, counters | `DynamicToolset` with fresh-instance factory |
| **Per-agent-call fresh** | Sub-agents should not interfere with parent state | Browser sessions in delegation | llm-do's `CallScope` |
| **Snapshot from parent** | Sub-agent starts where parent left off but can't mutate parent state | Browser with current URL carried over | No built-in mechanism |
| **Inherited from parent** | Sub-agents should share parent's context | Database transactions, rate limiters | Explicit plumbing through `deps` |

PydanticAI currently offers two: global (static toolset) and per-run (DynamicToolset with a well-behaved factory). llm-do adds per-agent-call via `CallScope`. Snapshot and inherited require manual plumbing.

The recurring pattern across the spectrum: the toolset provides a default behavior (share or isolate), and the **agent author overrides at the composition site** — passing the same instance for sharing, wrapping in a factory for isolation. The framework's job is to make both paths explicit and easy, not to pick one for all cases.

A traits system (see [Traits API proposal](https://github.com/pydantic/pydantic-ai/blob/traits-api-research/traits-research-report.md), [issue #4303](https://github.com/pydantic/pydantic-ai/issues/4303)) that doesn't model these lifecycle policies will inherit the same ambiguity. `Trait.get_toolset(ctx: RunContext)` could return any of these — but the framework can't validate or enforce the lifecycle contract because it doesn't know which policy the trait intends.

## Open Questions

- Should llm-do expose the lifecycle policy choice explicitly in `AgentSpec` or toolset registration? Something like `toolset("browser", lifecycle="per_call")` vs `toolset("pool", lifecycle="shared")`?
- For database transactions, is `__aenter__`/`__aexit__` alignment with agent call lifecycle sufficient, or does this need explicit transaction boundary management in the harness?
- Could the "inherited from parent" pattern work through `RunContext[deps]` — the sub-agent receives the parent's transaction via dependency injection?
- How do parallel tool calls interact with stateful toolsets? If two tool calls to the same browser execute concurrently, the state is corrupted. (PydanticAI's tool execution model and `sequential` tool flag are relevant here.)

---

Relevant Notes:
- [toolset-state-prevents-treating-pydanticai-agents-as-global](./toolset-state-prevents-treating-pydanticai-agents-as-global.md) — the upstream issue that motivates this catalog
- [proposed-toolset-lifecycle-resolution-for-pydanticai](./proposed-toolset-lifecycle-resolution-for-pydanticai.md) — three-layer proposal for addressing these lifecycle gaps in PydanticAI
- [llm-do-vs-pydanticai-runtime](./llm-do-vs-pydanticai-runtime.md) — per-call isolation as a key llm-do differentiator over vanilla PydanticAI

Topics:
- [index](./index.md)
- [pydanticai-upstream-index](./pydanticai-upstream-index.md)
