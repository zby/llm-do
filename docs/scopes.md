# Scopes and Toolset State

llm-do has three scopes that govern resource lifecycle and state isolation. Understanding these scopes is essential for toolset design.

## The Three Scopes

```
SESSION (Runtime)
└── CALL (entry invocation)
    ├── Turn 1 (prompt -> response)
    │   └── Child Call (nested worker)
    ├── Turn 2 (prompt -> response)
    └── Turn 3 (prompt -> response)
```

### Session Scope

**Lifetime**: Process start to exit. One `Runtime` per session.

**What lives here**:
- `Runtime` instance and `RuntimeConfig`
- Usage tracking, message log
- Approval callback and session-level approval cache

Sessions are not persisted—each CLI invocation is a separate session.

### Call Scope

**Lifetime**: From `Runtime.run_entry()` until it returns.

**What lives here**:
- `CallFrame` (prompt, messages, depth, active toolsets)
- Toolset instances (created fresh per call)
- Handle-based resources (DB transactions, browser sessions)

The key property: **all state created during a call is cleaned up when that call ends**. Toolset contexts exit, sessions close, handles release. The next call starts fresh.

**Naming vs instances**: Toolsets are referenced by name in worker config (declaring capability), but actual instances are created per call. Parent and child calls never share toolset instances.

### Turn Scope

**Lifetime**: One prompt → response within a call.

Turns update the `CallFrame` prompt. At depth 0, message history accumulates across turns. Nested worker calls always start with fresh history.

| Scope | Lifetime | Created | Cleaned Up |
|-------|----------|---------|------------|
| Session | Process | CLI starts | Process exits |
| Call | Entry invocation | `run_entry()` | Call returns |
| Turn | Prompt→response | Agent invoked | Response returned |

## Toolset Instances Are Per-Call

Toolsets are registered as factories in `TOOLSETS`. Each call gets a fresh instance:

```python
from pydantic_ai.tools import RunContext
from llm_do.runtime import CallContext

def build_tools(_ctx: RunContext[CallContext]):
    return MyToolset(config={"base_path": "/data"})

TOOLSETS = {"my_tools": build_tools}
```

Why per-call? If toolsets were shared, recursive workers would leak state:

```
Worker A (call 1)
  └── Worker A (call 2)  ← would see call 1's transaction handles
```

Per-call instances make each invocation self-contained.

## Sharing Expensive Resources

Some resources are expensive to create: connection pools, browser instances, HTTP clients. The factory pattern solves this: **capture shared resources in the closure, instantiate per-call state in the toolset**.

```python
# Connection pool created once at module load
pool = ConnectionPool(max_connections=10)

def build_database_tools(_ctx):
    # Fresh toolset instance per call, shared pool
    return DatabaseToolset(pool)

TOOLSETS = {"database": build_database_tools}
```

This gives you:
- **Shared**: The connection pool (expensive, thread-safe)
- **Isolated**: The transaction map inside each toolset instance

## Handle-Based State

Some toolsets need multiple concurrent resources within a single call. Handles make that state explicit:

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
        return self._transactions[txn].execute(sql).fetchall()

    def commit(self, txn: str) -> None:
        conn = self._transactions.pop(txn)
        conn.execute("COMMIT")
        self._pool.release(conn)
```

Handles keep the resource lifecycle in the LLM-visible control flow.

## Cleanup Protocol

Toolsets may implement `__aenter__`/`__aexit__` for lifecycle cleanup. The runtime
enters/exits toolsets per call:

```python
async def __aexit__(self, exc_type, exc, tb) -> None:
    for conn in self._transactions.values():
        conn.execute("ROLLBACK")
        self._pool.release(conn)
    self._transactions.clear()
```

## Design Guidance

- **Prefer stateless toolsets** when possible
- **Use handles** when multiple resources coexist in one call
- **Capture expensive resources in factories**, isolate per-call state in instances
- **Implement __aexit__** to release forgotten handles

## Chat Mode

Chat mode (`--chat`) carries message history across turns by passing it back into `run_entry()`. This enables conversational continuity at depth 0. Toolset instances still follow per-call lifetimes.

---

See also: [architecture](architecture.md) for runtime details.
