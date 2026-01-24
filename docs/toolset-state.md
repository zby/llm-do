# Toolset State and Isolation

Toolsets in llm-do follow two complementary patterns:

1. **Per-call instances (framework concern)**
2. **Handle-based state (toolset concern)**

These patterns solve different problems and are meant to be used together.

---

## Per-Call Toolset Instances

Toolsets are registered by name as `ToolsetSpec` factories. The name is a
run-scoped declaration of capability, while the instances are created per call.
Each call gets a fresh instance created from the factory at execution time.
This provides an isolation boundary:

- Parent and child calls never share toolset instance state
- Handle maps, caches, and open resources stay per call
- Worker-to-worker tool calls use a separate `WorkerToolset` wrapper per call

```python
from llm_do.runtime import ToolsetSpec

# tools.py

def build_tools():
    return MyToolset(config={"base_path": "/data"})

my_tools = ToolsetSpec(factory=build_tools)
```

### Why Per-Call?

If toolsets were shared across calls, recursive or nested workers would share
state in ways that break isolation:

```
Worker A (call 1)
  └── Worker A (call 2)  ← would share toolset instances from call 1
```

With shared instances:
- Handle maps leak between calls (call 2 sees call 1's transaction handles)
- Cleanup runs only once, not per call
- Debugging becomes unpredictable—state from one call affects another

Per-call instances make each invocation self-contained. The LLM in call 2
cannot accidentally reference handles from call 1 because they exist in
separate toolset instances.

---

## Sharing Expensive Resources via Factories

Some resources are expensive to create: database connection pools, browser
instances, API clients with connection pooling. Creating these per call
would be wasteful.

The factory pattern solves this: **capture shared resources in the factory
closure, instantiate per-call state in the toolset**.

```python
from llm_do.runtime import ToolsetSpec

# tools.py

# Expensive resource created once at module load
pool = ConnectionPool(max_connections=10)

def build_database_tools():
    # Each call gets a fresh toolset instance...
    # ...but they all share the same connection pool
    return DatabaseToolset(pool)

database = ToolsetSpec(factory=build_database_tools)
```

This gives you both:
- **Shared**: The connection pool (expensive, thread-safe, reusable)
- **Isolated**: The transaction map inside each `DatabaseToolset` instance

The same pattern works for any expensive-to-create resource:

```python
# Browser instance shared across calls
browser = playwright.chromium.launch()

def build_browser_tools():
    return BrowserToolset(browser)  # Pages map is per-call

browser_tools = ToolsetSpec(factory=build_browser_tools)
```

```python
# HTTP client with connection pooling shared across calls
http_client = httpx.AsyncClient()

def build_api_tools():
    return ApiToolset(http_client)  # Request state is per-call

api = ToolsetSpec(factory=build_api_tools)
```

**Rule of thumb**: If a resource is expensive to create and safe to share
(connection pools, browser instances, HTTP clients), capture it in the
factory closure. Per-call state (handle maps, transaction tracking, request
context) belongs in the toolset instance.

---

## Handle-Based State (Within a Worker)

Some toolsets need multiple concurrent resources (transactions, sessions,
streams). A handle pattern makes that state explicit and keeps it in the
LLM-visible control flow.

### Database Example

```python
class DatabaseToolset(FunctionToolset):
    def __init__(self, pool):
        self._pool = pool
        self._transactions = {}

    def begin(self) -> str:
        handle = f"txn_{uuid4().hex[:8]}"
        conn = self._pool.checkout()
        conn.execute("BEGIN")
        self._transactions[handle] = conn
        return handle

    def execute(self, txn: str, sql: str):
        if txn not in self._transactions:
            raise ValueError(f"Unknown transaction: {txn}")
        return self._transactions[txn].execute(sql).fetchall()

    def commit(self, txn: str) -> None:
        conn = self._transactions.pop(txn)
        conn.execute("COMMIT")
        self._pool.release(conn)
```

### Browser Example

```python
class BrowserToolset(FunctionToolset):
    def __init__(self, browser):
        self._browser = browser
        self._pages = {}

    def open_page(self, url: str) -> str:
        handle = f"page_{uuid4().hex[:8]}"
        page = self._browser.new_page(url)
        self._pages[handle] = page
        return handle

    def click(self, page: str, selector: str) -> None:
        if page not in self._pages:
            raise ValueError(f"Unknown page handle: {page}")
        self._pages[page].click(selector)

    def close_page(self, page: str) -> None:
        self._pages.pop(page).close()
```

Handles keep the resource lifecycle explicit, so the LLM controls when to open,
use, and close resources within the worker boundary.

---

## Cleanup Protocol

Toolsets may implement an optional `cleanup()` method (sync or async). The
runtime calls cleanup on all toolset instances after each call and logs errors
without failing the run.

Use cleanup to release any forgotten handles, close sessions, and free pooled
resources.

```python
class DatabaseToolset(FunctionToolset):
    async def cleanup(self) -> None:
        for conn in self._transactions.values():
            conn.execute("ROLLBACK")
            self._pool.release(conn)
        self._transactions.clear()
```

---

## Design Guidance

- **Prefer stateless toolsets** when possible
- **Use handles** when multiple resources must coexist inside one worker
- **Rely on per-call instances** for isolation between calls
- **Implement cleanup** to prevent resource leaks after each call
