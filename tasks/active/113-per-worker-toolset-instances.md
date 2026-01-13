# Per-Worker Toolset Instances with Handle-Based State

## Status
ready for implementation

## Prerequisites
- [x] none

## Goal
Implement per-worker toolset instances for isolation, combined with handle-based explicit state management within each instance. Add run-scoped cleanup for handles.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/registry.py` (toolset instantiation, _merge_toolsets)
  - `llm_do/toolsets/builtins.py` (built-in toolset factory)
  - `llm_do/toolsets/loader.py` (build_toolsets)
  - `llm_do/runtime/worker.py` (WorkerToolset, worker execution)
  - `llm_do/runtime/shared.py` (Runtime, run lifecycle)
  - `llm_do/toolsets/approval.py` (per-tool approval config)
  - `docs/architecture.md`, `README.md`
- How to verify:
  - Handles from Worker A cannot be used by Worker B
  - Cleanup is called at run end
  - Documentation accurately describes both patterns

## Decision Record: The Journey

### Original Problem
Toolset instances are shared globally, causing:
- State leakage between workers (browser sessions, DB connections)
- Approval config mutation affecting other workers

### First Pivot: "Stateless Toolsets"
Proposed: Make toolsets stateless and use handles for any state needed, with approval config defined globally per toolset name (so multiple named variants can carry different approval policies).

**Rationale:** Keep the framework simple (avoid per-worker scoping machinery) while allowing global approval config via distinct toolset names.

**Clarification:** The "stateless" framing was misleading. We don't need to ban stateful toolsets, and we do need them for DB connections and document/web browsing. The real requirement was global approval config by name, not eliminating statefulness.

### Second Pivot: "Explicit State / No Hidden State"
Reframed: State is fine, but must be explicit via handles (visible to LLM), not implicit per-instance (hidden).

**Example:**
```python
txn = db.begin()           # Returns handle - LLM sees this
db.execute(txn, sql)       # LLM passes handle back
db.commit(txn)             # LLM controls lifecycle
```

**Problem discovered:** With shared toolset instances, Worker B could use Worker A's handle (accidentally or through hallucination). Even with unguessable UUIDs, handles could leak between workers.

### Final Decision: Both Patterns Together

**Per-worker toolset instances** solve isolation:
- Each worker gets its own toolset instance
- Handle maps are per-worker, can't leak across workers
- Framework manages instance lifecycle

**Handle-based state** solves explicit state management:
- State within a worker's toolset is explicit via handles
- LLM sees and controls state lifecycle
- Cleanup releases forgotten handles at run end

These are complementary, not alternatives:
- Instances → isolation boundary (framework concern)
- Handles → explicit state (toolset design concern)

## Architecture

### Two Layers

```
┌─────────────────────────────────────────────────────┐
│                     Run                              │
│  ┌──────────────────┐    ┌──────────────────┐       │
│  │    Worker A      │    │    Worker B      │       │
│  │  ┌────────────┐  │    │  ┌────────────┐  │       │
│  │  │ DBToolset  │  │    │  │ DBToolset  │  │       │
│  │  │ instance A │  │    │  │ instance B │  │       │
│  │  │            │  │    │  │            │  │       │
│  │  │ handles:   │  │    │  │ handles:   │  │       │
│  │  │  txn_123   │  │    │  │  txn_456   │  │       │
│  │  └────────────┘  │    │  └────────────┘  │       │
│  └──────────────────┘    └──────────────────┘       │
│                                                      │
│  Worker A's txn_123 is invisible to Worker B        │
└─────────────────────────────────────────────────────┘
```

### Toolset Instantiation Scope

| Scope | When | Use Case |
|-------|------|----------|
| `per_worker` (default) | New instance per worker | Stateful tools needing isolation |
| `per_run` | Shared within run | Connection pools, shared caches |
| `global` | Shared across runs | Truly stateless config-only toolsets |

### Handle-Based State Within Instance

Even with per-worker instances, tools should use handles for explicit state:

```python
class DatabaseToolset:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool                           # Shared pool reference
        self._transactions: dict[str, Connection] = {}  # Per-instance handle map

    def begin(self) -> str:
        handle = f"txn_{uuid4().hex[:8]}"
        self._transactions[handle] = self._pool.checkout()
        return handle
```

Why handles even with per-worker instances?
- Multiple transactions within one worker need tracking
- Explicit lifecycle (LLM decides when to commit/rollback)
- Cleanup can release forgotten handles

## Implementation

### Toolset Factory/Spec Pattern

```python
@dataclass
class ToolsetSpec:
    """Specification for creating toolset instances."""
    factory: Callable[[], AbstractToolset]
    scope: Literal["per_worker", "per_run", "global"] = "per_worker"

# Registry stores specs, not instances
toolset_specs: dict[str, ToolsetSpec] = {
    "database": ToolsetSpec(
        factory=lambda: DatabaseToolset(pool),
        scope="per_worker",
    ),
    "shell_readonly": ToolsetSpec(
        factory=lambda: ShellToolset(config=READONLY_RULES),
        scope="global",  # Stateless, can share
    ),
}
```

### Instance Cache

```python
class ToolsetCache:
    def __init__(self):
        self._global: dict[str, AbstractToolset] = {}
        self._per_run: dict[str, AbstractToolset] = {}
        self._per_worker: dict[tuple[str, str], AbstractToolset] = {}  # (worker_name, toolset_name)

    def get(self, spec: ToolsetSpec, name: str, worker_name: str) -> AbstractToolset:
        if spec.scope == "global":
            if name not in self._global:
                self._global[name] = spec.factory()
            return self._global[name]
        elif spec.scope == "per_run":
            if name not in self._per_run:
                self._per_run[name] = spec.factory()
            return self._per_run[name]
        else:  # per_worker
            key = (worker_name, name)
            if key not in self._per_worker:
                self._per_worker[key] = spec.factory()
            return self._per_worker[key]
```

### Cleanup Protocol

```python
async def cleanup(self) -> None:
    """Called at run end to release handle-based resources."""
    pass

# Runtime calls cleanup on all per_worker and per_run instances at run end
```

## Handle Pattern Example

```python
class DatabaseToolset(FunctionToolset):
    """Database toolset with per-worker isolation and handle-based transactions."""

    scope = "per_worker"  # Each worker gets own instance

    def __init__(self, pool: ConnectionPool):
        self._pool = pool
        self._transactions: dict[str, Connection] = {}

    def begin_transaction(self) -> str:
        """Start transaction. Returns handle (visible to LLM)."""
        conn = self._pool.checkout()
        handle = f"txn_{uuid4().hex[:8]}"
        self._transactions[handle] = conn
        conn.execute("BEGIN")
        return handle

    def execute(self, txn_handle: str, sql: str) -> list[dict]:
        """Execute SQL. Requires handle from begin_transaction."""
        if txn_handle not in self._transactions:
            raise ValueError(f"Unknown transaction: {txn_handle}")
        return self._transactions[txn_handle].execute(sql).fetchall()

    def commit(self, txn_handle: str) -> None:
        """Commit and release. LLM controls when this happens."""
        conn = self._transactions.pop(txn_handle)
        conn.execute("COMMIT")
        self._pool.release(conn)

    async def cleanup(self) -> None:
        """Rollback uncommitted transactions at run end."""
        for conn in self._transactions.values():
            try:
                conn.execute("ROLLBACK")
                self._pool.release(conn)
            except Exception:
                pass
        self._transactions.clear()
```

## Tasks

### Per-Worker Instantiation
- [ ] Define `ToolsetSpec` with factory and scope
- [ ] Implement `ToolsetCache` with per_worker/per_run/global scoping
- [ ] Update registry to store specs, instantiate on demand
- [ ] Update built-in toolsets with appropriate scopes

### Cleanup Lifecycle
- [ ] Define `cleanup()` protocol (optional async method)
- [ ] Call cleanup on all scoped instances at run end
- [ ] Handle cleanup errors gracefully (log, don't propagate)

### Documentation
- [ ] Create `docs/toolset-state.md` explaining both patterns:
  - Per-worker isolation (framework provides)
  - Handle-based state (toolset implements)
- [ ] Add section to `docs/architecture.md` with reference
- [ ] Update `README.md` with brief note and reference
- [ ] Include DB and browser examples

### Testing
- [ ] Test handle isolation between workers
- [ ] Test cleanup called at run end
- [ ] Test scope options (per_worker, per_run, global)

## Current State
Task resurrected after exploring alternatives. The "stateless toolsets" approach had an isolation flaw. Final design combines per-worker instances with handle-based state. Ready for implementation.

## Notes
- Approval config should be global per toolset spec/name (so distinct names can carry distinct policies)
- Built-in toolsets like `shell_readonly` can be `global` scope (truly stateless)
- `filesystem_project` needs `per_worker` scope (different base paths per worker)
- The handle pattern is valuable within per-worker instances for multi-resource management
