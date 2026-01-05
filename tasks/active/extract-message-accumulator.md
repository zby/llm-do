# Extract MessageAccumulator from CallFrame

## Status
backlog

## Prerequisites
- [ ] Two-Object API task completed (`tasks/backlog/two-object-api.md`)

## Goal
Move message history from per-call state (`CallFrame`) to global config (`RuntimeConfig`) using a `MessageAccumulator` pattern, following the existing `UsageCollector` pattern.

**Before:**
```python
@dataclass
class CallFrame:
    toolsets: list[AbstractToolset]
    model: ModelType
    depth: int
    prompt: str
    messages: list[Any]  # mutable, in per-call scope

# Mutation pattern in Worker.call():
runtime.messages[:] = list(child_runtime.messages)
```

**After:**
```python
class MessageAccumulator:
    """Thread-safe container for conversation messages."""

    def __init__(self) -> None:
        self._messages: list[Any] = []

    def update(self, msgs: list[Any]) -> None:
        self._messages[:] = msgs

    def get(self) -> list[Any]:
        return list(self._messages)

    def as_history(self) -> list[Any] | None:
        """Return messages for history, or None if empty."""
        return list(self._messages) if self._messages else None

@dataclass(frozen=True)
class RuntimeConfig:
    cli_model: ModelType | None
    run_approval_policy: RunApprovalPolicy
    max_depth: int
    on_event: EventCallback | None
    verbosity: int
    usage: UsageCollector
    messages: MessageAccumulator  # NEW: moved from CallFrame

@dataclass
class CallFrame:
    toolsets: list[AbstractToolset]
    model: ModelType
    depth: int
    prompt: str
    # messages removed - now in RuntimeConfig
```

## Rationale

Messages aren't really per-call state - they're a shared accumulator for the whole run:

1. Only top-level workers (depth ≤ 1) use message history for multi-turn conversations
2. The pattern already exists with `UsageCollector`
3. Moving messages to `RuntimeConfig` enables making `CallFrame` truly immutable later
4. Clearer semantics: messages accumulate at run level, not per-worker

Current mutation pattern in `worker.py`:
```python
def _update_message_history(runtime: WorkerRuntimeProtocol, result: Any) -> None:
    """Update message history in-place to keep shared references intact."""
    runtime.messages[:] = _get_all_messages(result)
```

This in-place mutation exists because:
- Multi-turn conversations need message accumulation
- Only applies at depth ≤ 1 (see `_should_use_message_history`)
- Parent and child currently share the same list reference

## Context

- Relevant files:
  - `llm_do/runtime/context.py` - `RuntimeConfig`, `CallFrame`, `WorkerRuntime`
  - `llm_do/runtime/worker.py` - `_update_message_history()`, `_should_use_message_history()`, message access in `Worker.call()`
  - `llm_do/runtime/runner.py` - `run_invocable()` passes `message_history`
  - `llm_do/runtime/contracts.py` - `WorkerRuntimeProtocol.messages` property

- Reference implementation: `UsageCollector` in `context.py`:
  ```python
  class UsageCollector:
      """Thread-safe sink for RunUsage objects."""

      def __init__(self) -> None:
          self._lock = threading.Lock()
          self._usages: list[RunUsage] = []

      def create(self) -> RunUsage:
          usage = RunUsage()
          with self._lock:
              self._usages.append(usage)
          return usage

      def all(self) -> list[RunUsage]:
          with self._lock:
              return list(self._usages)
  ```

## Tasks

- [ ] Add `MessageAccumulator` class to `context.py`:
  ```python
  class MessageAccumulator:
      """Thread-safe container for conversation messages.

      Unlike UsageCollector which appends, this replaces the entire
      message list (conversation history is replaced, not accumulated).
      """

      def __init__(self, initial: list[Any] | None = None) -> None:
          self._lock = threading.Lock()
          self._messages: list[Any] = list(initial) if initial else []

      def update(self, msgs: list[Any]) -> None:
          """Replace all messages."""
          with self._lock:
              self._messages[:] = msgs

      def get(self) -> list[Any]:
          """Return a copy of current messages."""
          with self._lock:
              return list(self._messages)

      def as_history(self) -> list[Any] | None:
          """Return messages for history param, or None if empty."""
          with self._lock:
              return list(self._messages) if self._messages else None
  ```

- [ ] Add `messages: MessageAccumulator` field to `RuntimeConfig`:
  ```python
  @dataclass(frozen=True)
  class RuntimeConfig:
      cli_model: ModelType | None
      run_approval_policy: RunApprovalPolicy
      max_depth: int = 5
      on_event: EventCallback | None = None
      verbosity: int = 0
      usage: UsageCollector = field(default_factory=UsageCollector)
      messages: MessageAccumulator = field(default_factory=MessageAccumulator)
  ```

- [ ] Remove `messages` field from `CallFrame`:
  ```python
  @dataclass(slots=True)
  class CallFrame:
      toolsets: list[AbstractToolset[Any]]
      model: ModelType
      depth: int = 0
      prompt: str = ""
      # messages field removed
  ```

- [ ] Update `CallFrame.fork()` and `clone_same_depth()` - remove messages handling

- [ ] Update `WorkerRuntime`:
  - Change `messages` property to delegate to `self.config.messages.get()`
  - Update `__init__` to pass initial messages to `RuntimeConfig.messages`
  - Update `from_entry()` to initialize `MessageAccumulator` with provided history

- [ ] Update `WorkerRuntimeProtocol` in `contracts.py`:
  - Keep `messages` property (returns `list[Any]`)
  - Tools should not notice any change

- [ ] Update `_update_message_history()` in `worker.py`:
  ```python
  def _update_message_history(runtime: WorkerRuntimeProtocol, result: Any) -> None:
      """Update message history via the shared accumulator."""
      # Access the accumulator through config (or via runtime property)
      runtime.config.messages.update(_get_all_messages(result))
  ```

  Or if accessing via WorkerRuntime:
  ```python
  def _update_message_history(runtime: WorkerRuntimeProtocol, result: Any) -> None:
      # If runtime exposes update method:
      runtime.update_messages(_get_all_messages(result))
  ```

- [ ] Update `Worker.call()` message handling:
  - Remove `runtime.messages[:] = list(child_runtime.messages)` pattern
  - Use `config.messages.update()` instead
  - Child workers share the same `config.messages` accumulator (no forking needed)

- [ ] Update `run_invocable()` in `runner.py`:
  - Pass `message_history` to `MessageAccumulator` initialization

- [ ] Remove `_should_use_message_history()` helper or simplify:
  - With shared accumulator, the depth check may move elsewhere
  - Consider: only update accumulator for top-level calls

## Verification

```bash
uv run pytest tests/runtime/ -v
uv run pytest tests/ -k message -v  # any message-related tests
```

Test multi-turn conversation still works:
```python
# Pseudocode test
runtime = WorkerRuntime.from_entry(worker, messages=[...])
result1 = await runtime.run(worker, {"input": "first"})
# messages should be accumulated
result2 = await runtime.run(worker, {"input": "second"})
# should include history from first turn
```

## Risks / Edge Cases

- Thread safety: `MessageAccumulator` must be thread-safe (use lock like `UsageCollector`)
- Multi-turn: Messages must accumulate correctly across turns at top level
- Nested workers: Child workers should NOT update message history (depth > 1)
- Empty history: `as_history()` returns `None` for empty to avoid issues with some providers

## Notes

- This is Phase 2 of a 3-phase refactoring:
  - Phase 1: Two-Object API (prerequisite)
  - Phase 2: Extract MessageAccumulator (this task)
  - Phase 3: Immutable CallState (next task)

- After this task, `CallFrame` has no mutable shared state, enabling immutability in Phase 3

- The `_should_use_message_history(runtime)` check (`depth <= 1`) may need rethinking:
  - Option A: Keep check, only call `messages.update()` for top-level
  - Option B: Always update, but only use history for top-level agent runs
  - Recommend Option A for clarity
