---
description: Concrete examples for each toolset state category, evaluating whether the proposed stateful flag + copy-before-run mechanism resolves each case
areas: [pydanticai-upstream-index]
status: current
last_verified: 2026-02-18
pydanticai_version: "1.26.0"
---

# The stateful flag resolves simple accumulation but not session or composition-site cases

Evaluates the [proposed fix](https://github.com/pydantic/pydantic-ai/issues/4347) — a `stateful` flag on `AbstractToolset` that opts into copy-before-run via custom `copy()` or `dataclasses.replace()` — against concrete examples from each category in [toolset-state-spectrum-from-stateless-to-transactional](./toolset-state-spectrum-from-stateless-to-transactional.md).

## The proposal

```python
class AbstractToolset:
    stateful: bool = False  # opt-in

    def copy(self) -> Self:
        """Override for custom copy logic. Default: dataclasses.replace(self)."""
        return dataclasses.replace(self)
```

In `Agent._get_toolset()`, if `toolset.stateful`, call `toolset.copy()` before each run.

## Category 1: Pure functional tools

```python
@dataclass
class HashToolset(AbstractToolset):
    # stateful = False (default)

    async def call_tool(self, name, tool_args, ctx, tool):
        if name == "sha256":
            return hashlib.sha256(tool_args["text"].encode()).hexdigest()
        if name == "md5":
            return hashlib.md5(tool_args["text"].encode()).hexdigest()
```

**Verdict: N/A.** No state, no copy needed. `stateful=False` is correct. The flag doesn't interfere.

## Category 2: External side effects (stateless toolset, stateful world)

```python
@dataclass
class NotificationToolset(AbstractToolset):
    webhook_url: str
    # stateful = False (default)

    async def call_tool(self, name, tool_args, ctx, tool):
        if name == "send_slack":
            requests.post(self.webhook_url, json={"text": tool_args["message"]})
            return "sent"
```

**Verdict: N/A.** Config is immutable, side effects are external. `stateful=False` is correct. No issue.

## Category 3: Shared long-lived resources

```python
@dataclass
class PoolSearchToolset(AbstractToolset):
    pool: asyncpg.Pool  # expensive, shared by design
    # stateful = False (default) — MUST be False

    async def call_tool(self, name, tool_args, ctx, tool):
        if name == "query":
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(tool_args["sql"])
                return [dict(r) for r in rows]
```

**Verdict: N/A — but risky if misused.** `stateful=False` is correct. If someone naively sets `stateful=True`, `dataclasses.replace()` would create a second toolset referencing the same pool (harmless but wasteful). A custom `copy()` that tried to create a new pool would be destructive. The flag defaults to safe behavior, so this is fine — but worth documenting that shared resources must NOT opt in.

## Category 4: Per-run accumulating state

### 4a: Search cache

```python
@dataclass
class CachingSearchToolset(AbstractToolset):
    stateful = True
    cache: dict[str, str] = field(default_factory=dict)
    call_count: int = 0

    async def call_tool(self, name, tool_args, ctx, tool):
        self.call_count += 1
        query = tool_args["query"]
        if query not in self.cache:
            self.cache[query] = await web_search(query)
        return self.cache[query]
```

**With `dataclasses.replace()` (shallow copy):** FAILS. The new instance shares the same `cache` dict by reference. Run 2 sees run 1's cache entries. `call_count` (int, immutable) is correctly isolated.

**With custom `copy()`:**

```python
def copy(self):
    return CachingSearchToolset(cache={}, call_count=0)
```

WORKS — but this is exactly what a factory function does. The developer writes the same "create fresh" logic; it just lives in `copy()` instead of a lambda.

### 4b: Rate limiter

```python
@dataclass
class RateLimitedToolset(AbstractToolset):
    stateful = True
    max_calls: int = 10
    _calls_this_run: int = field(default=0, init=False)
    _timestamps: list[float] = field(default_factory=list, init=False)

    async def call_tool(self, name, tool_args, ctx, tool):
        self._calls_this_run += 1
        if self._calls_this_run > self.max_calls:
            raise ToolError(f"Rate limit exceeded: {self.max_calls} calls per run")
        self._timestamps.append(time.time())
        return await self._inner_call(name, tool_args)
```

**With `dataclasses.replace()`:** FAILS. `_timestamps` list is shared by reference. `_calls_this_run` (int) works correctly — but only because ints are immutable.

**With custom `copy()`:** WORKS — `return RateLimitedToolset(max_calls=self.max_calls)`.

**Sub-agent question:** Should a sub-agent share the parent's rate limit (global quota) or get its own? A class-level `stateful=True` can't express "share with children but isolate across runs." The developer would need to pass the same instance for shared quota, defeating the flag's automatic copy.

### 4c: Conversation memory / tool call log

```python
@dataclass
class AuditToolset(AbstractToolset):
    """Wraps another toolset and logs all calls."""
    stateful = True
    inner: AbstractToolset
    log: list[dict] = field(default_factory=list)

    async def call_tool(self, name, tool_args, ctx, tool):
        result = await self.inner.call_tool(name, tool_args, ctx, tool)
        self.log.append({"tool": name, "args": tool_args, "result": str(result)[:200]})
        return result
```

**With `dataclasses.replace()`:** FAILS. `log` list shared by reference. Worse: `inner` toolset is also shared — if `inner` is itself stateful, the shallow copy provides no isolation for the wrapped toolset either.

**With custom `copy()`:** Partially works — must also copy `inner` if it's stateful: `return AuditToolset(inner=self.inner.copy() if self.inner.stateful else self.inner, log=[])`. This works but requires the wrapper to understand the statefulness of its children — a composability burden.

## Category 5: Stateful sessions

### 5a: Browser session

```python
@dataclass
class BrowserToolset(AbstractToolset):
    stateful = True
    _browser: Browser | None = field(default=None, init=False)
    _page: Page | None = field(default=None, init=False)

    async def __aenter__(self):
        self._browser = await playwright.chromium.launch()
        self._page = await self._browser.new_page()
        return self

    async def call_tool(self, name, tool_args, ctx, tool):
        if name == "navigate":
            await self._page.goto(tool_args["url"])
            return f"Navigated to {tool_args['url']}"
        if name == "click":
            await self._page.click(tool_args["selector"])
            return "Clicked"
        if name == "get_text":
            return await self._page.text_content(tool_args["selector"])
```

**With `dataclasses.replace()`:** FAILS. Both `_browser` and `_page` are `None` (pre-`__aenter__`), so the copy gets uninitialized state. If called after `__aenter__`, the copy shares the same browser/page objects — two runs drive the same browser tab.

**With custom `copy()`:** Must create a genuinely new browser session:

```python
def copy(self):
    return BrowserToolset()  # __aenter__ will create fresh browser
```

This works, and the lifecycle is handled: PydanticAI's run path enters the `CombinedToolset` via `async with`, and `CombinedToolset.__aenter__` enters each child toolset — including any copies produced by the stateful mechanism. So `copy()` returns an uninitialized `BrowserToolset()`, and the framework's `__aenter__` call launches the browser.

### 5b: REPL with persistent environment

```python
@dataclass
class REPLToolset(AbstractToolset):
    stateful = True
    env: dict[str, Any] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)

    async def call_tool(self, name, tool_args, ctx, tool):
        if name == "exec":
            code = tool_args["code"]
            self.history.append(code)
            exec(code, self.env)
            return self.env.get("_result", "executed")
```

**With `dataclasses.replace()`:** FAILS. `env` and `history` dicts shared by reference.

**With custom `copy()`:** WORKS for fresh-per-run: `return REPLToolset()`.

**Sub-agent delegation:** If a parent agent runs `exec("x = 42")` then delegates to a sub-agent — should the sub-agent see `x`? A snapshot pattern would need:

```python
def copy(self):
    return REPLToolset(env=dict(self.env), history=list(self.history))
```

But this is a deep copy of the env dict — any mutable values in the env would still be shared. The `stateful` flag can't distinguish between "fresh per run" and "snapshot from parent."

## Category 6: Database transactions

```python
@dataclass
class TransactionalToolset(AbstractToolset):
    pool: asyncpg.Pool
    _conn: asyncpg.Connection | None = field(default=None, init=False)
    _tx: asyncpg.Transaction | None = field(default=None, init=False)

    async def __aenter__(self):
        self._conn = await self.pool.acquire()
        self._tx = self._conn.transaction()
        await self._tx.start()
        return self

    async def __aexit__(self, exc_type, *args):
        if exc_type:
            await self._tx.rollback()
        else:
            await self._tx.commit()
        await self.pool.release(self._conn)

    async def call_tool(self, name, tool_args, ctx, tool):
        return await self._conn.fetch(tool_args["sql"])
```

**The flag can't help here.** The correct behavior depends on the composition site:

- **Shared transaction** (`stateful=False`): Sub-agent participates in parent's transaction. Pass the same instance.
- **Isolated transaction** (`stateful=True` with `copy()` → fresh toolset): Sub-agent gets its own connection and transaction.
- **Nested transaction** (savepoint): Neither flag value works. Requires `copy()` that creates a savepoint on the parent's connection — a semantic operation the framework can't provide generically.

Setting `stateful=True` would force ALL usages to get isolated transactions. The developer who wants shared transactions in one sub-agent and isolated in another can't express this with a class-level flag.

## Category 7: Coordinated multi-resource state

```python
# Agent with browser + database + cache
agent = Agent('model', toolsets=[
    BrowserToolset(),            # stateful=True → fresh per run
    TransactionalToolset(pool),  # stateful=??? → depends on usage
    CachingSearchToolset(),      # stateful=True → fresh per run
])
```

**The flag works per-toolset but can't coordinate across toolsets.** If the browser navigates to a form and the transaction fills it with queried data, failure coordination (should the transaction roll back if navigation fails?) is outside the flag's scope. Each toolset's `copy()` runs independently.

## Summary

| Category | Example | `dataclasses.replace()` | Custom `copy()` | Composition-site resolved? |
|----------|---------|------------------------|-----------------|---------------------------|
| 1. Pure functional | HashToolset | N/A | N/A | N/A |
| 2. External effects | NotificationToolset | N/A | N/A | N/A |
| 3. Shared resources | PoolSearchToolset | N/A (must NOT opt in) | N/A | N/A |
| 4a. Cache | CachingSearchToolset | FAILS (shared dict) | WORKS | No — can't share cache with sub-agent |
| 4b. Rate limiter | RateLimitedToolset | FAILS (shared list) | WORKS | No — can't share quota with sub-agent |
| 4c. Audit wrapper | AuditToolset | FAILS (shared list + inner) | Partial — must know inner's statefulness | No |
| 5a. Browser | BrowserToolset | FAILS (shared browser) | WORKS (lifecycle handled by CombinedToolset) | No — can't snapshot |
| 5b. REPL | REPLToolset | FAILS (shared env) | WORKS for fresh | No — snapshot needs deep copy |
| 6. Transaction | TransactionalToolset | FAILS | Can't express shared vs isolated | No — composition-site decision |
| 7. Multi-resource | Combined | Per-toolset only | Per-toolset only | No — no cross-toolset coordination |

## Assessment

The `stateful` flag with **custom `copy()`** resolves **Categories 4a, 4b, 5a, 5b** for the simple case (fresh-per-run). This covers the most common pain point: toolsets that accumulate state and leak it across runs of a global agent.

**`dataclasses.replace()` as fallback is actively dangerous** — it creates a false sense of isolation while sharing mutable containers by reference. If the fallback is kept, it should at minimum warn or require that all mutable fields have `copy()` semantics. Better: require custom `copy()` when `stateful=True` and error if it's not provided.

**What the flag cannot do:**
- Express composition-site decisions (shared vs isolated for sub-agents)
- Handle lifecycle (`__aenter__`/`__aexit__`) on copied toolsets
- Coordinate across multiple stateful toolsets
- Distinguish "fresh per run" from "snapshot from parent"

These limitations aren't reasons to reject the proposal — they're scope boundaries. The flag solves the cross-run leakage problem (the original issue). The composition-site and sub-agent problems are separate concerns that likely need different mechanisms (e.g., `for_sub_agent()` hook, or explicit sharing/isolation at the wiring site). Note: `Agent.run(toolsets=...)` exists but is additive only — it extends the base set, it can't replace toolsets for a specific run.

## Proposals for the remaining gaps

The `stateful` flag covers cross-run leakage (the original issue). The gaps below are distinct problems that need distinct mechanisms. Grouped by what we'd propose to PydanticAI vs what stays in application land.

### Tier 1: Improve the stateful flag itself

**Require `copy()` override when `stateful=True`.** Drop the `dataclasses.replace()` fallback — it silently fails for any toolset with mutable containers (which is all of them, since that's why they're stateful). Error at agent construction if a toolset declares `stateful=True` but doesn't override `copy()`:

```python
class AbstractToolset:
    stateful: bool = False

    def copy(self) -> Self:
        if self.stateful:
            raise NotImplementedError(
                f"{type(self).__name__} declares stateful=True but doesn't implement copy(). "
                "Override copy() to return a fresh instance."
            )
        return self  # stateless toolsets return themselves
```

This catches the common mistake (declaring `stateful=True` and assuming the framework handles it) at construction time, not at runtime via subtle state leakage.

**Cost:** Slightly more work for the toolset author. **Benefit:** No false safety. The author explicitly writes what "fresh" means for their toolset.

### Tier 2: ~~Framework enters lifecycle on copies~~ Already handled (Categories 5a, 5b)

**Update (2026-02-18):** PydanticAI's current run path already enters all toolsets via `CombinedToolset.__aenter__`, which recursively enters each child. This means copies produced by the `stateful` mechanism would automatically get their `__aenter__`/`__aexit__` called — the same way `DynamicToolset` factories already work. No additional framework change is needed for this tier.

The BrowserToolset case works: `copy()` returns `BrowserToolset()` (uninitialized), `CombinedToolset.__aenter__` calls `BrowserToolset.__aenter__()` which launches the browser, and `__aexit__` cleans up at run end.

### Tier 3: Composition-site override via `for_sub_agent()` (Categories 4 sub-agent, 6)

The `stateful` flag is a class-level property — it controls cross-run behavior. But sub-agent delegation needs a **per-delegation** decision. Add a `for_sub_agent()` hook (see [proposed-toolset-lifecycle-resolution-for-pydanticai](./proposed-toolset-lifecycle-resolution-for-pydanticai.md) Layer 3):

```python
class AbstractToolset:
    def for_sub_agent(self, ctx: RunContext) -> 'AbstractToolset':
        """Return toolset instance for a sub-agent.

        Default: return self (shared).
        Override for isolation or snapshot semantics.
        """
        return self
```

This lets each toolset encode domain knowledge about sub-agent isolation:

```python
class CachingSearchToolset(AbstractToolset):
    stateful = True

    def copy(self):
        return CachingSearchToolset()  # fresh per run

    def for_sub_agent(self, ctx):
        return self  # share cache warmth with sub-agents

class BrowserToolset(AbstractToolset):
    stateful = True

    def copy(self):
        return BrowserToolset()  # fresh per run

    def for_sub_agent(self, ctx):
        # Snapshot: sub-agent starts at parent's URL but gets own tab
        new = BrowserToolset()
        new._start_url = self._page.url if self._page else None
        return new

class TransactionalToolset(AbstractToolset):
    def for_sub_agent(self, ctx):
        return self  # default: share the transaction

class IsolatedTransactionalToolset(TransactionalToolset):
    def for_sub_agent(self, ctx):
        return TransactionalToolset(pool=self.pool)  # own connection
```

The agent author can still override at the wiring site:

```python
# Use toolset's default sub-agent policy
sub_agent = Agent(toolsets=[browser_toolset])

# Override: force fresh regardless of toolset's preference
sub_agent = Agent(toolsets=[DynamicToolset(lambda ctx: BrowserToolset())])

# Override: force sharing regardless of toolset's preference
sub_agent = Agent(toolsets=[parent_toolset])  # same instance, no for_sub_agent()
```

The key insight: `for_sub_agent()` and `copy()` serve different purposes. `copy()` handles cross-run isolation (same agent, different runs). `for_sub_agent()` handles cross-agent isolation (parent delegates to child). These are orthogonal — a toolset might want fresh-per-run (`copy()` returns new) but shared-with-sub-agents (`for_sub_agent()` returns self), like the caching search example.

**Cost:** New protocol method on AbstractToolset. **Benefit:** Covers categories 4 (sub-agent cache/quota sharing), 5 (snapshot), and 6 (transaction sharing) without framework-level complexity.

### Tier 4: Wrapper composability (Category 4c — AuditToolset)

Toolsets that wrap other toolsets (audit loggers, rate limiters, approval wrappers) face a composability problem: when the outer toolset is copied, its inner toolset must also be handled correctly.

**Proposal: Convention, not mechanism.** The framework can't know the wrapper topology. Instead, document the pattern:

```python
@dataclass
class AuditToolset(AbstractToolset):
    stateful = True
    inner: AbstractToolset
    log: list[dict] = field(default_factory=list)

    def copy(self):
        # Recursively handle inner toolset's statefulness
        inner_copy = self.inner.copy() if self.inner.stateful else self.inner
        return AuditToolset(inner=inner_copy, log=[])

    def for_sub_agent(self, ctx):
        inner_sub = self.inner.for_sub_agent(ctx)
        return AuditToolset(inner=inner_sub, log=[])  # sub-agent gets own audit log
```

This is a burden on the wrapper author, but it's inherent — the wrapper knows its relationship to the inner toolset, the framework doesn't. The convention is: **if you wrap a toolset, propagate `copy()` and `for_sub_agent()` calls**.

PydanticAI could add a `WrappingToolset` base class that handles this:

```python
class WrappingToolset(AbstractToolset):
    """Base for toolsets that wrap other toolsets."""
    inner: AbstractToolset

    def copy(self):
        raise NotImplementedError  # wrapper must define what fresh means

    def for_sub_agent(self, ctx):
        # Default: propagate to inner, rewrap
        inner_sub = self.inner.for_sub_agent(ctx)
        new = self.copy()
        new.inner = inner_sub
        return new
```

**Cost:** New optional base class + documentation. **Benefit:** Composability pattern becomes visible and consistent.

### Tier 5: What stays in application land (Category 7)

**Cross-toolset coordination is the developer's responsibility.** The framework cannot know that a transaction should roll back when browser navigation fails — that's application semantics. Two patterns to document:

**Pattern A: Coordination through deps.** Pass shared state via `RunContext[deps]`:

```python
@dataclass
class WorkflowState:
    """Shared state passed as deps."""
    conn: asyncpg.Connection
    tx: asyncpg.Transaction
    browser_page: Page

# Both toolsets read from deps instead of owning the resource
class DBToolset(AbstractToolset):
    async def call_tool(self, name, tool_args, ctx, tool):
        conn = ctx.deps.conn  # shared connection from deps
        return await conn.fetch(tool_args["sql"])

class BrowserToolset(AbstractToolset):
    async def call_tool(self, name, tool_args, ctx, tool):
        page = ctx.deps.browser_page  # shared page from deps
        await page.goto(tool_args["url"])
```

The coordination logic lives in the application's run setup, not in the toolsets. Each toolset is stateless — the shared state is in deps.

**Pattern B: Orchestrator manages lifecycle.** Code entry (not LLM) manages resource lifecycle and passes toolset instances:

```python
async def main(input_data, runtime):
    async with asyncpg.create_pool(dsn) as pool:
        async with pool.acquire() as conn:
            tx = conn.transaction()
            await tx.start()
            try:
                result = await runtime.call_agent("worker", {
                    "input": input_data,
                }, toolsets=[
                    DBToolset(conn=conn),
                    BrowserToolset(),
                ])
                await tx.commit()
            except Exception:
                await tx.rollback()
                raise
```

The agent doesn't manage transactions — the orchestrator does. This is llm-do's code entry pattern: deterministic orchestration in Python, LLM reasoning only where needed.

**Cost:** Zero framework changes. **Benefit:** Clear separation — framework handles common toolset lifecycle, developer handles cross-resource coordination.

### Summary of proposals

| Gap | Mechanism | Where it lives | Effort |
|-----|-----------|---------------|--------|
| Shallow copy trap | Require `copy()` override | `stateful` flag PR | Small |
| ~~Lifecycle on copies~~ | Already handled by `CombinedToolset.__aenter__` | N/A | N/A |
| Sub-agent isolation | `for_sub_agent()` hook | AbstractToolset protocol | Medium |
| Wrapper composability | `WrappingToolset` base + convention | Optional base class + docs | Small |
| Cross-resource coordination | `deps` pattern + code entry | Application land (document only) | Zero |

Tiers 1 and 3 are layered — Tier 3 builds on Tier 1. Tier 2 is already handled by PydanticAI's existing `CombinedToolset` lifecycle. Tiers 4 and 5 are independent. Together they cover the full spectrum without trying to make the framework omniscient about domain-specific lifecycle decisions.

## How this works for a framework like llm-do

llm-do sits between PydanticAI and user/plugin toolsets. It controls Agent construction but must accept arbitrary toolsets — from built-in factories, user `tools.py` files, and plugins. This creates specific constraints that affect how the `stateful` flag would interact with the framework.

### Current architecture (with approval wrapping)

```
AgentSpec (static, in registry)
    │
    │  CallScope.for_agent()
    ▼
_prepare_toolsets_for_run()
    │  For each toolset:
    │    DynamicToolset → wrap factory output with ApprovalToolset
    │    AbstractToolset → wrap directly with ApprovalToolset
    │    ToolsetFunc → wrap in DynamicToolset + ApprovalToolset
    ▼
_build_agent(spec, runtime, toolsets=wrapped)
    │  new Agent constructed with wrapped toolsets
    ▼
agent.run() → result
    │
Agent discarded
```

Every call constructs a new PydanticAI Agent. This is forced because:
1. Toolsets must be wrapped with approval before `Agent(toolsets=...)` binding
2. `DynamicToolset` factories produce fresh instances that need wrapping
3. PydanticAI's `Agent.run(toolsets=...)` is additive only — extends the base set, can't replace

**However:** [we-want-to-get-rid-of-approval-wrapping](./we-want-to-get-rid-of-approval-wrapping.md). Two upstream PydanticAI proposals — `deferred_tool_handler` and Traits `before_tool_call` hooks — would eliminate the `ApprovalToolset` wrapping entirely. Approval would become a hook in the agent loop, not a toolset wrapper. This fundamentally changes how the `stateful` flag interacts with llm-do.

### What the stateful flag would change

If PydanticAI copies stateful toolsets per-run internally (in `Agent._get_toolset()`), the question becomes: **could llm-do construct the Agent once and reuse it?**

The answer depends on whether llm-do still wraps toolsets.

**With approval wrapping (current state):** The `stateful` flag hits the Category 4c wrapper composability problem. PydanticAI copies the outer `ApprovalToolset`, not the inner stateful toolset. The flag is invisible unless `ApprovalToolset` propagates `stateful`/`copy()` to its inner toolset — which it currently doesn't. This would require either convention (wrappers must propagate) or mechanism (framework walks the wrapper chain).

**Without approval wrapping (target state):** If approval moves to a hook (`deferred_tool_handler` or Traits `before_tool_call`), there are no wrappers. Toolsets are passed directly to `Agent(toolsets=...)`. PydanticAI's `stateful` flag sees the actual toolset, not a wrapper. **The wrapper propagation problem vanishes entirely.**

This makes the no-wrapping path even more valuable — it's not just about deleting ~440 lines of wrapping code, it's a prerequisite for the `stateful` flag to work correctly in any framework that wraps toolsets today.

### The reentrant agent case

Consider an agent that calls itself recursively (or agent A → B → A):

```
Agent A runs
  └── A calls itself
        └── A calls itself again
```

**With per-call Agent construction (current):** Each recursive call gets a fresh Agent with fresh toolsets. Safe but expensive — repeats model resolution, instruction assembly, output schema validation.

**With reusable Agent + stateful flag:** The same Agent object is reused. PydanticAI copies stateful toolsets per-run. Each recursive call gets fresh stateful toolset copies but shares stateless toolsets.

```
Agent A (constructed once, reused)
├── HashToolset (stateless) ─── shared across all calls ✓
├── CachingSearch (stateful) ── copy() per run ✓
└── ApprovalToolset wrapping CachingSearch
    └── must propagate copy() to inner ⚠️
```

**This works IF:**
1. ApprovalToolset propagates `stateful`/`copy()` to the inner toolset
2. PydanticAI enters `__aenter__`/`__aexit__` on copied toolsets
3. Plugin toolsets correctly declare `stateful=True` when they have state

**Condition 3 is the risk for plugin toolsets.** A plugin author who forgets `stateful=True` ships a leaky toolset. llm-do's current approach (always-fresh via factory for built-ins) is safer — it isolates by default.

### The plugin trust boundary

llm-do accepts toolsets from four sources with different trust levels:

| Source | Example | Who controls `stateful`? | Reused across runs? |
|--------|---------|-------------------------|---------------------|
| Built-in | FileSystemToolset, ShellToolset | llm-do — always wrapped in factory today | No (factory) |
| User `tools.py` (factory) | `build_calc_tools()` function | User — returns FunctionToolset from factory | No (factory) |
| User `tools.py` (static) | `TOOLSETS = {"calc": MyToolset()}` | User — provides AbstractToolset instance | Yes — reused across runs |
| Plugin | Arbitrary AbstractToolset | Plugin author — llm-do can't control | Yes — reused across runs |

For built-ins and user factories, llm-do already ensures per-run freshness. The `stateful` flag doesn't change anything — it's redundant.

For **user static instances and plugins**, the flag matters. Both sources can provide long-lived `AbstractToolset` instances that are reused across runs. If these have hidden mutable state and don't declare `stateful=True`, they leak. User static instances (`project/discovery.py` registers them at module level) carry the same risk as plugins — the distinction is trust, not mechanism.

**Two strategies:**

**Strategy A: Trust the flag (opt-in isolation).** Accept plugin toolsets as-is. If they declare `stateful=True`, PydanticAI copies them per-run. If they don't, they're shared. Plugin authors are responsible for correctness. This is the PydanticAI ecosystem norm — consistent across frameworks.

**Strategy B: Default-isolate plugins (opt-out sharing).** Wrap all plugin toolsets in a factory regardless of their `stateful` flag. This is safer but means `stateful=False` toolsets get unnecessarily reconstructed. It also means llm-do ignores the flag, defeating its purpose.

**Strategy C: Hybrid — isolate by default, let plugins opt out.** Wrap plugin toolsets in a factory by default. If a plugin toolset declares `shared=True` (e.g., an MCP server or connection pool), respect it and pass the instance directly. This inverts the default: isolation is assumed, sharing is declared.

Strategy C matches llm-do's existing behavior (all built-ins are factory-wrapped) and extends it to plugins. The `stateful` flag becomes one signal among several — llm-do uses its own isolation policy and falls back to the flag for edge cases.

### Could we stop creating Agents per-call?

The Agent-per-call pattern is driven by three forces:

1. **Toolset wrapping** — approval must be applied before `Agent(toolsets=...)`
2. **Per-run freshness** — stateful toolsets need fresh instances
3. **`Agent.run(toolsets=...)` is additive, not replacement** — it extends the base toolset list rather than replacing it; `Agent.override(toolsets=...)` replaces but is test-oriented (uses `contextvars`, docs say "particularly useful when testing")

The `stateful` flag addresses force 2 (PydanticAI handles per-run freshness internally).

**If approval wrapping goes away** (via `deferred_tool_handler` or Traits hooks), force 1 disappears. Toolsets are passed directly to Agent, no wrapping step needed. Force 3 is weaker than originally stated — `run(toolsets=...)` exists but is additive (extends, doesn't replace), and `override(toolsets=...)` replaces but is test-oriented. Neither provides a clean production-grade per-run replacement path.

**If the Agent is reusable** (constructed once with toolsets, reused across runs), the `stateful` flag handles per-run freshness internally. This works for the simple case — sequential runs of the same agent. For recursive calls (agent calls itself), each re-entry triggers a new `agent.run()`, and PydanticAI copies stateful toolsets for each run. The Agent object is shared; the stateful toolset instances are not.

```
Agent A (constructed once)
├── HashToolset (stateful=False) ─── same instance across all runs ✓
├── CachingSearch (stateful=True) ── copy() called per run ✓
└── BrowserToolset (stateful=True) ─ copy() + __aenter__ per run ✓

A.run("task 1")  → CachingSearch.copy(), BrowserToolset.copy()
  └── A.run("subtask")  → CachingSearch.copy(), BrowserToolset.copy()
A.run("task 2")  → CachingSearch.copy(), BrowserToolset.copy()
```

**What remains for llm-do:** Even without wrapping and with per-run freshness handled by the flag, llm-do still needs per-call Agent construction for one reason: the `DynamicToolset` factory pattern. User `tools.py` files export `TOOLSETS = {"name": build_tools_func}` — these are factory functions, not toolset instances. llm-do currently wraps them in `DynamicToolset` and passes the approval-wrapping result to the Agent.

Without approval wrapping, the factory functions could be passed to `DynamicToolset` directly at Agent construction time — PydanticAI calls the factory per-run. **This would allow Agent-once construction for agents whose toolsets are all either static instances or `DynamicToolset`-wrapped factories.**

The remaining edge case: toolsets that need llm-do-specific runtime context at factory time (e.g., `CallContext` as deps). These factories receive `RunContext[CallContext]` and use it to access `runtime.call_agent()`. The `DynamicToolset` factory naturally receives `RunContext` per-run, so this still works — the factory is called per-run with fresh context.

**Bottom line:** The combination of (1) no approval wrapping + (2) `stateful` flag + (3) `DynamicToolset` for user factories would let llm-do construct Agents once and reuse them. Per-call construction becomes unnecessary. This is a significant simplification — it eliminates `_build_agent()` from the hot path and makes recursive/reentrant agents cheap.

### Recommendation for the issue reply

Support the `stateful` flag proposal with these caveats:

1. **Require `copy()` override** — `dataclasses.replace()` is a trap for mutable state
2. ~~**Enter lifecycle on copies**~~ Already handled — PydanticAI's run path enters `CombinedToolset` which recursively enters children, including copies
3. **Specify wrapper behavior** — any wrapping toolset must propagate `stateful`/`copy()`, otherwise the flag is invisible through wrappers. This becomes less critical if approval moves to hooks (no more `ApprovalToolset` wrappers), but matters for any `PrefixedToolset`, `CombinedToolset`, or other wrappers in the ecosystem
4. **Acknowledge scope boundary** — the flag solves cross-run leakage; composition-site decisions (sub-agent sharing vs isolation) are a separate concern that needs `for_sub_agent()` or an explicit sharing/isolation mechanism at the wiring site

The no-wrapping future ([we-want-to-get-rid-of-approval-wrapping](./we-want-to-get-rid-of-approval-wrapping.md)) makes the `stateful` flag more viable for frameworks like llm-do. With approval as a hook rather than a wrapper, toolsets pass through to PydanticAI unwrapped — the flag sees the actual toolset, not a wrapper layer. Combined with `DynamicToolset` for user factories, this could eliminate per-call Agent construction entirely.

---

Relevant Notes:
- [toolset-state-spectrum-from-stateless-to-transactional](./toolset-state-spectrum-from-stateless-to-transactional.md) — the taxonomy this evaluation follows
- [toolset-state-prevents-treating-pydanticai-agents-as-global](./toolset-state-prevents-treating-pydanticai-agents-as-global.md) — the upstream issue motivating the proposal
- [proposed-toolset-lifecycle-resolution-for-pydanticai](./proposed-toolset-lifecycle-resolution-for-pydanticai.md) — three-layer resolution proposal
- [we-want-to-get-rid-of-approval-wrapping](./we-want-to-get-rid-of-approval-wrapping.md) — eliminating wrapping makes the stateful flag work cleanly for frameworks

Topics:
- [index](./index.md)
