# Runtime Scopes: Global vs Worker

**Status: IMPLEMENTED** (see commits a145973, 5bcb770, 95cf388)

## Summary

This analysis led to a 3-phase refactoring:
1. **Phase 1**: Two-object API - `Invocable.call(input, config, state, run_ctx)`
2. **Phase 2**: MessageAccumulator - diagnostic sink for all messages (NOT for conversation context)
3. **Phase 3**: Frozen CallConfig - immutable configuration nested in CallFrame

**Key insight from implementation:** Messages must stay in CallFrame (not move to global scope) because worker isolation requires each worker to have its own messages list. Parent workers only see tool call/result, not child's internal conversation.

---

## Original Problem Statement

The runtime has two distinct scopes that are currently mixed in the API:

1. **Global Scope** - Constant for the entire run, shared across all workers
2. **Worker Scope** - Per-worker state that forks on each spawn

The current `WorkerRuntime` facade obscures this distinction, making it harder to reason about what's shared vs. what's isolated.

## Final Implementation

```
RuntimeConfig (frozen, shared)       CallConfig (frozen, per-worker)
├── cli_model                        ├── toolsets (tuple)
├── run_approval_policy              ├── model (resolved)
├── max_depth                        └── depth
├── on_event
├── verbosity                        CallFrame (mutable state)
├── usage (UsageCollector)           ├── config: CallConfig
└── message_log (MessageAccumulator) ├── prompt
                                     └── messages (list)
         └───────────────┬───────────────┘
                         │
                 WorkerRuntime (facade)
```

**Invocable.call() signature:**
```python
async def call(
    self,
    input_data: Any,
    config: RuntimeConfig,     # global scope (immutable, shared)
    state: CallFrame,          # per-call scope (has frozen CallConfig + mutable messages)
    run_ctx: RunContext[WorkerRuntimeProtocol],
) -> Any: ...
```

**Worker isolation (verified):**
- Parent workers only see tool call/result in their messages
- Child worker's internal messages stay isolated
- Multi-turn accumulation works correctly at entry level (depth ≤ 1)

## Tensions

### 1. Facade Obscures Semantics

When you access `runtime.model` vs `runtime.max_depth`, they look identical but have fundamentally different semantics:
- `max_depth` is global, immutable, same for everyone
- `model` is per-call, resolved, can differ between parent and child

### 2. Protocol Conflation

`WorkerRuntimeProtocol` defines a single contract mixing both concerns:

```python
class WorkerRuntimeProtocol(Protocol):
    # Global concerns
    @property
    def max_depth(self) -> int: ...
    @property
    def on_event(self) -> EventCallback | None: ...

    # Per-call concerns
    @property
    def depth(self) -> int: ...
    @property
    def model(self) -> ModelType: ...
```

### 3. Spawn Semantics

`spawn_child()` lives on `WorkerRuntime`, making it look like it creates a whole new runtime. In reality, it only forks the `CallFrame` while sharing `RuntimeConfig`.

### 4. Message History Policy

`_should_use_message_history()` checks `runtime.depth` to decide sharing behavior. This policy is:
- Encoded as a function, not configuration
- Mixing "what depth am I at" (fact) with "should I share history" (policy)

### 5. Model Resolution Spread

Model can come from three sources with priority:
1. Worker definition (`worker.model`)
2. CLI override (`cli_model`)
3. Parent runtime (`runtime.model`)

This resolution logic is spread across `select_model()`, `Worker.call()`, and `WorkerRuntime.from_entry()`.

---

## Resolution Options

### Option A: Explicit Two-Object API

Workers receive both objects explicitly:

```python
class Invocable(Protocol):
    async def call(
        self,
        input_data: Any,
        config: GlobalConfig,      # immutable, shared
        state: WorkerState,        # mutable, per-call
        run_ctx: RunContext[...],
    ) -> Any: ...
```

**Pros:**
- Maximum clarity about what's global vs per-call
- Type system enforces the distinction
- Easy to reason about in isolation

**Cons:**
- Breaking change to all Invocable implementations
- More parameters to pass around
- Workers that only need one scope still receive both

**Verdict:** Clean but invasive. Best if we're already doing a major refactor.

---

### Option B: Nested Access Pattern

Keep facade but expose structure:

```python
class WorkerRuntime:
    @property
    def global_(self) -> RuntimeConfig:
        return self.config

    @property
    def frame(self) -> CallFrame:
        return self._frame

# Usage becomes explicit:
runtime.global_.on_event(...)   # clearly global
runtime.frame.depth             # clearly per-call
runtime.frame.model             # clearly per-call
```

Keep backward-compatible properties that delegate:
```python
@property
def depth(self) -> int:
    return self.frame.depth  # deprecated, use frame.depth
```

**Pros:**
- Non-breaking (old code still works)
- Makes distinction visible when you want it
- Gradual migration path

**Cons:**
- Two ways to access same data
- Deprecation warnings add noise
- Still a facade, just more transparent

**Verdict:** Good transitional approach. Allows gradual adoption.

---

### Option C: Immutable State with Explicit Fork

Make `CallFrame` immutable, return new instances:

```python
@dataclass(frozen=True)
class CallFrame:
    toolsets: tuple[AbstractToolset[Any], ...]
    model: ModelType
    depth: int
    prompt: str
    messages: tuple[Any, ...]  # immutable

    def with_incremented_depth(self) -> CallFrame:
        return replace(self, depth=self.depth + 1, messages=())

    def with_toolsets(self, toolsets: Sequence[AbstractToolset]) -> CallFrame:
        return replace(self, toolsets=tuple(toolsets))
```

**Pros:**
- Clear data flow, no hidden mutation
- Easy to test (compare before/after)
- Functional style, thread-safe by construction

**Cons:**
- Messages need special handling (currently mutated in place)
- More allocations (probably negligible)
- Bigger conceptual shift

**Verdict:** Elegant but requires rethinking message accumulation.

---

### Option D: Split Protocols

Define separate protocols for each scope:

```python
class GlobalRuntimeProtocol(Protocol):
    """Read-only access to run-wide configuration."""
    @property
    def max_depth(self) -> int: ...
    @property
    def on_event(self) -> EventCallback | None: ...
    @property
    def verbosity(self) -> int: ...
    @property
    def run_approval_policy(self) -> RunApprovalPolicy: ...


class WorkerStateProtocol(Protocol):
    """Per-worker call state."""
    @property
    def depth(self) -> int: ...
    @property
    def model(self) -> ModelType: ...
    @property
    def prompt(self) -> str: ...
    @property
    def messages(self) -> list[Any]: ...

    def spawn_child(self, ...) -> WorkerStateProtocol: ...


class WorkerRuntimeProtocol(GlobalRuntimeProtocol, WorkerStateProtocol):
    """Combined protocol (backward compatible)."""
    pass
```

**Pros:**
- Can type functions that only need global vs only need state
- Backward compatible (existing code uses combined protocol)
- Documents the conceptual split

**Cons:**
- More types to understand
- `spawn_child` returns `WorkerStateProtocol` but needs access to global config

**Verdict:** Good for documentation and gradual typing improvements.

---

### Option E: Context Variables

Use Python's `contextvars` for global scope:

```python
from contextvars import ContextVar

_global_config: ContextVar[RuntimeConfig] = ContextVar('global_config')

class WorkerState:
    """Only per-call state, global accessed via contextvar."""

    @property
    def global_config(self) -> RuntimeConfig:
        return _global_config.get()

    # ... per-call properties
```

**Pros:**
- Reduces parameter passing
- Global truly is global (within async context)
- Clean separation

**Cons:**
- Implicit state (harder to test, reason about)
- contextvars have async subtleties
- Harder to run multiple isolated runtimes in same process

**Verdict:** Risky. Implicit state causes debugging pain.

---

### Option F: Scope-Aware Spawn

Keep current structure but make spawn semantics clearer:

```python
class WorkerRuntime:
    def spawn_child(self, ...) -> WorkerRuntime:
        """Fork the worker state; global config is shared (not copied)."""
        # Current implementation, but with clearer docs/naming

    @property
    def is_root(self) -> bool:
        """True if this is the top-level runtime (depth=0 or 1)."""
        return self.depth <= 1
```

Add explicit methods for common patterns:
```python
def should_persist_messages(self) -> bool:
    """Policy: only root workers persist message history."""
    return self.is_root
```

**Pros:**
- Minimal code change
- Encapsulates policies as methods
- Self-documenting via method names

**Cons:**
- Doesn't address fundamental conflation
- Just better docs, not better structure

**Verdict:** Quick win, but doesn't solve the core issue.

---

## Combining Two-Object API with Immutable CallState

Option A (Two-Object API) and Option C (Immutable State) are compatible, but there's a complication: **message history mutation**.

### The Problem: Message Propagation

Current code mutates messages in place to propagate conversation history:

```python
# After child worker completes, copy messages back to parent
if _should_use_message_history(child_runtime):
    runtime.messages[:] = list(child_runtime.messages)
```

This pattern exists because:
- Multi-turn conversations need message accumulation
- Only applies at depth ≤ 1 (top-level workers)
- Parent and child share the same list reference

### Solutions for Immutable State + Messages

**Option 1: Messages as mutable exception**

```python
@dataclass(frozen=True)
class CallState:
    toolsets: tuple[AbstractToolset, ...]  # immutable
    model: ModelType
    depth: int
    prompt: str
    messages: list[Any]  # mutable container, shared reference
```

Verdict: Pragmatic but impure. The "frozen" is a lie.

**Option 2: Thread state through returns**

```python
async def call(...) -> tuple[Any, CallState]:
    ...
    return result, final_state
```

Verdict: Clean functional style but changes Invocable return type.

**Option 3: MessageAccumulator pattern (recommended)**

```python
class MessageAccumulator:
    """Thread-safe, mutable container for conversation messages."""

    def __init__(self) -> None:
        self._messages: list[Any] = []

    def update(self, msgs: list[Any]) -> None:
        self._messages[:] = msgs

    def get(self) -> list[Any]:
        return list(self._messages)

@dataclass(frozen=True)
class RunConfig:
    cli_model: ModelType | None
    run_approval_policy: RunApprovalPolicy
    max_depth: int
    on_event: EventCallback | None
    verbosity: int
    usage: UsageCollector
    messages: MessageAccumulator  # NEW: lives in global scope
```

Verdict: Clean separation. Messages become a global-scope accumulator shared across the call tree. Follows the existing `UsageCollector` pattern.

**Option 4: Recognize "Conversation" as third scope**

```
RunConfig (global)     - approval, events, verbosity, usage
CallState (per-call)   - depth, model, toolsets, prompt
Conversation (shared)  - messages accumulator
```

Verdict: Most conceptually accurate but adds complexity.

### Why Option 3 Works

Messages aren't really per-call state - they're a shared accumulator for the whole run:

1. Only top-level workers (depth ≤ 1) use message history
2. The pattern already exists with `UsageCollector`
3. Makes `CallState` truly immutable with no exceptions
4. No return type changes needed

---

## Refactoring Sequence (COMPLETED)

### Phase 1: Two-Object API ✓

Split config/state at the Invocable boundary while keeping `WorkerRuntime` as deps type for tools:

```python
class Invocable(Protocol):
    async def call(
        self,
        input_data: Any,
        config: RunConfig,                    # explicit global
        state: CallState,                     # explicit per-call
        run_ctx: RunContext[WorkerRuntime],   # tools unchanged
    ) -> Any: ...
```

**Changes required:**
- Update `Invocable` protocol in `contracts.py`
- Update `Worker.call()` and `ToolInvocable.call()`
- Update `WorkerRuntime._execute()` to pass both objects

**Scope:** ~5 files, ~50-100 lines

### Phase 2: MessageAccumulator ✓ (revised scope)

**Original plan:** Move messages from CallFrame to RuntimeConfig.

**Actual implementation:** Messages stay in CallFrame for correct worker isolation. MessageAccumulator added as a **diagnostic sink** for testing/logging (similar to UsageCollector).

```python
@dataclass(frozen=True)
class RunConfig:
    ...
    messages: MessageAccumulator  # moved from CallState

@dataclass
class CallState:
    toolsets: list[AbstractToolset]
    model: ModelType
    depth: int
    prompt: str
    # messages removed
```

**Changes required:**
- Add `MessageAccumulator` class
- Move `messages` field to `RunConfig`
- Update message access patterns in `Worker`

### Phase 3: Immutable CallState

Now safe to freeze:

```python
@dataclass(frozen=True)
class CallState:
    toolsets: tuple[AbstractToolset, ...]  # tuple, not list
    model: ModelType
    depth: int
    prompt: str

    def with_depth(self, depth: int) -> CallState:
        return replace(self, depth=depth)

    def with_toolsets(self, toolsets: Sequence[AbstractToolset]) -> CallState:
        return replace(self, toolsets=tuple(toolsets))
```

**Changes required:**
- Make `CallState` frozen
- Replace mutation with `replace()` calls
- Update `fork()` and `clone_same_depth()` patterns

---

## Naming Recommendation

Rename types to emphasize identity semantics:

| Current | Proposed | Rationale |
|---------|----------|-----------|
| `RuntimeConfig` | `RunConfig` | "The run" - one per execution |
| `CallFrame` | `CallState` | "The call" - per worker invocation |
| `WorkerRuntime` | `WorkerRuntime` | Keep as facade (backward compat) |

---

## Key Insight

The distinction isn't just about mutability. It's about **identity**:

- **Global scope** = "the run" - one run, one config, multiple workers
- **Worker scope** = "the call" - each worker invocation has its own frame

When a worker spawns a child:
- They share the same **run identity** (same approval policy, same event sink)
- They have different **call identities** (different depth, different model, fresh messages)

Naming suggestion: Consider `RunConfig` + `CallState` to emphasize this.
