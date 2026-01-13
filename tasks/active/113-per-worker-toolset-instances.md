# Per-Worker Toolset Instances with Handle-Based State

## Status
ready for implementation

## Prerequisites
- [x] none

## Goal
Implement per-worker toolset instances for isolation, with run-scoped cleanup for handle-based resources. Document the handle pattern for stateful toolsets.

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
  - Same toolset name in different workers creates separate instances
  - Handles from Worker A cannot be used by Worker B (when using handle pattern)
  - Cleanup is called on all toolset instances at run end
  - Documentation accurately describes both patterns

## Decision Record: The Journey

### Original Problem (Ticket Created)
Could not have both read-only and read-write filesystem toolsets in the same project. Toolsets were singletons by name—a worker couldn't choose between permission levels for the same underlying resource.

### Workaround (Ticket to Backlog)
Created separate named instances as a workaround:
- `filesystem_cwd`, `filesystem_cwd_ro`
- `filesystem_project`, `filesystem_project_ro`

Workers choose which variant they need via the `toolsets` list in their definition. This unblocked immediate needs, and the ticket was moved to backlog.

### Discovery: Configuration Explosion
The workaround doesn't scale. Adding more variations leads to combinatorial blow-up:
- Different base paths (cwd, project root, custom directories)
- Different permission levels (read-only, read-write, append-only)
- Different rule sets

Pre-creating all combinations is unsustainable. We need toolsets instantiated per-worker with worker-specific configuration.

### Inherent Statefulness
Some toolsets genuinely need runtime state:
- Database connections and transactions
- Browser sessions for navigating large documents/web pages
- File handles for streaming content

Handle-based state makes this explicit—the LLM sees handles and controls their lifecycle:
```python
txn = db.begin()           # Returns handle - LLM sees this
db.execute(txn, sql)       # LLM passes handle back
db.commit(txn)             # LLM controls lifecycle
```

### The Isolation Problem
With shared toolset instances, handles can leak between workers. An LLM might hallucinate or accidentally reuse a handle name (`txn_123`) that exists in another worker's context. Even with UUID-based handles, cross-worker access is possible if the toolset instance is shared.

### Final Decision: Both Patterns Together

**Per-worker toolset instances** solve isolation:
- Each worker gets its own toolset instance
- Handle maps are per-worker, invisible to other workers
- Framework manages instance lifecycle

**Handle-based state** solves explicit state management:
- Multiple resources within one worker need tracking (e.g., multiple transactions)
- LLM sees and controls state lifecycle
- Cleanup releases forgotten handles at run end

These are complementary, not alternatives:
- Instances → isolation boundary (framework concern)
- Handles → explicit state within that boundary (toolset design concern)

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

### Toolset Instantiation

Each worker gets fresh toolset instances. This provides isolation—Worker A's handles are invisible to Worker B.

Future optimization: Add instance caching by scope (`per_worker`, `per_run`, `global`) to avoid recreating stateless toolsets.

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
    factory: Callable[[ToolsetBuildContext], AbstractToolset]

# Registry stores specs, not instances
toolset_specs: dict[str, ToolsetSpec] = {
    "database": ToolsetSpec(
        factory=lambda ctx: DatabaseToolset(pool),
    ),
    "shell_readonly": ToolsetSpec(
        factory=lambda ctx: ShellToolset(config=READONLY_RULES),
    ),
}
```

### Per-Worker Instantiation

Each worker gets fresh toolset instances created from specs:

```python
def build_toolsets_for_worker(
    toolset_names: list[str],
    specs: dict[str, ToolsetSpec],
    ctx: ToolsetBuildContext,
) -> list[AbstractToolset]:
    """Create fresh toolset instances for a worker."""
    return [specs[name].factory(ctx) for name in toolset_names]
```

### Cleanup Protocol

Toolsets may implement an optional `cleanup()` method for releasing handle-based resources at run end:

```python
class AbstractToolset:
    async def cleanup(self) -> None:
        """Called at run end to release resources. Override to implement."""
        pass
```

Runtime calls cleanup on all toolset instances at end of `run_invocable()`.

## Handle Pattern Example

Shows how a stateful toolset uses handles for explicit state management:

```python
class DatabaseToolset(FunctionToolset):
    """Database toolset with per-worker isolation and handle-based transactions."""

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

    def rollback(self, txn_handle: str) -> None:
        """Rollback and release. LLM controls when this happens."""
        conn = self._transactions.pop(txn_handle)
        conn.execute("ROLLBACK")
        self._pool.release(conn)
```

The `cleanup()` protocol (defined above) handles forgotten handles at run end.

## Tasks

### Per-Worker Instantiation
- [ ] Define `ToolsetSpec` dataclass with factory
- [ ] Update `build_builtin_toolsets()` to return specs instead of instances
- [ ] Update `_merge_toolsets()` to work with specs
- [ ] Update `build_toolsets()` in loader.py to instantiate from specs
- [ ] Wrap Python toolset instances in specs (factory returns the instance)
- [ ] Pass `ToolsetBuildContext` through resolution chain

### Cleanup Lifecycle
- [ ] Define `cleanup()` protocol (optional async method on toolsets)
- [ ] Track toolset instances created during run
- [ ] Call cleanup on all instances at end of `Runtime.run_invocable()`
- [ ] Handle cleanup errors gracefully (log, don't propagate)

### Documentation
- [ ] Create `docs/toolset-state.md` explaining both patterns:
  - Per-worker isolation (framework provides)
  - Handle-based state (toolset implements)
- [ ] Add section to `docs/architecture.md` with reference
- [ ] Include DB and browser examples

### Testing
- [ ] Test that same toolset name in different workers gets different instances
- [ ] Test handle isolation between workers
- [ ] Test cleanup called at run end

## Follow-on: Instance Caching

Deferred to a follow-on task:
- Instance caching by scope (`per_worker`, `per_run`, `global`) to avoid recreating stateless toolsets

## Notes
- Approval config is per toolset spec/name (distinct names can carry distinct policies)
- The handle pattern is valuable within per-worker instances for multi-resource management
- Factory receives `ToolsetBuildContext` for access to worker name, path, etc.
