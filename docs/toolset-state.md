# Toolset State and Isolation

Toolsets in llm-do follow two complementary patterns:

1. **Per-call instances (framework concern)**
2. **Handle-based state (toolset concern)**

These patterns solve different problems and are meant to be used together.

---

## Per-Call Toolset Instances

Toolsets are registered as `ToolsetSpec` factories. Each call gets a fresh
instance created from the factory at execution time. This provides an
isolation boundary:

- Parent and child calls never share toolset instance state
- Handle maps, caches, and open resources stay per call
- Worker-to-worker tool calls use a separate `WorkerToolset` wrapper per call

```python
from llm_do.runtime import ToolsetSpec

# tools.py

def build_tools(_ctx):
    return MyToolset(config={"base_path": "/data"})

my_tools = ToolsetSpec(factory=build_tools)
```

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
