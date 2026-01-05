# Add MessageAccumulator for Diagnostics

## Status
completed

## Prerequisites
- [x] Two-Object API task completed

## Goal
Add a `MessageAccumulator` to `RuntimeConfig` as a **diagnostic sink** for testing and logging. This captures all messages from all workers during a run, but workers do NOT read from it for conversation context.

**Key insight from verification:**
- Current message isolation is correct: child worker messages don't leak to parents
- Current multi-turn accumulation is correct: entry workers accumulate messages across turns
- `CallFrame.messages` should remain for per-worker conversation context
- `MessageAccumulator` is a separate observability layer (like `UsageCollector`)

**After:**
```python
class MessageAccumulator:
    """Thread-safe sink for capturing all messages across workers.

    Used for testing and logging - workers do NOT read from this
    for their conversation context.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._messages: list[tuple[str, int, Any]] = []  # (worker_name, depth, message)

    def append(self, worker_name: str, depth: int, message: Any) -> None:
        """Record a message from a worker."""
        with self._lock:
            self._messages.append((worker_name, depth, message))

    def all(self) -> list[tuple[str, int, Any]]:
        """Return all recorded messages."""
        with self._lock:
            return list(self._messages)

@dataclass(frozen=True)
class RuntimeConfig:
    cli_model: ModelType | None
    run_approval_policy: RunApprovalPolicy
    max_depth: int = 5
    on_event: EventCallback | None = None
    verbosity: int = 0
    usage: UsageCollector = field(default_factory=UsageCollector)
    message_log: MessageAccumulator = field(default_factory=MessageAccumulator)  # NEW
```

## Rationale

The `MessageAccumulator` serves a different purpose than `CallFrame.messages`:

| Aspect | `CallFrame.messages` | `MessageAccumulator` |
|--------|---------------------|---------------------|
| Scope | Per-worker conversation | All workers in run |
| Purpose | Conversation context | Testing & logging |
| Read by workers | Yes (depth ≤ 1) | No |
| Isolation | Parent doesn't see child's internal messages | Captures everything |

**Use cases for MessageAccumulator:**
1. **Testing**: Verify which messages were exchanged during a run
2. **Logging**: Debug complex multi-worker interactions
3. **Observability**: Track all LLM calls across nested workers

## Context

- Relevant files:
  - `llm_do/runtime/context.py` - `RuntimeConfig`, `UsageCollector` (reference pattern)
  - `llm_do/runtime/worker.py` - `Worker.call()` where messages are produced

- Reference implementation: `UsageCollector` in `context.py`

- Verified current behavior (see `/tmp/test_message_isolation.py`):
  - Parent workers only see tool call/result, not child's internal messages
  - Multi-turn conversations accumulate correctly at entry level

## Tasks

- [x] Add `MessageAccumulator` class to `context.py`:
  ```python
  class MessageAccumulator:
      """Thread-safe sink for capturing messages across all workers.

      Used for testing and logging. Workers do NOT read from this
      for their conversation context - that stays in CallFrame.messages.
      """

      def __init__(self) -> None:
          self._lock = threading.Lock()
          self._messages: list[tuple[str, int, Any]] = []

      def append(self, worker_name: str, depth: int, message: Any) -> None:
          """Record a message from a worker."""
          with self._lock:
              self._messages.append((worker_name, depth, message))

      def extend(self, worker_name: str, depth: int, messages: list[Any]) -> None:
          """Record multiple messages from a worker."""
          with self._lock:
              for msg in messages:
                  self._messages.append((worker_name, depth, msg))

      def all(self) -> list[tuple[str, int, Any]]:
          """Return all recorded messages."""
          with self._lock:
              return list(self._messages)

      def for_worker(self, worker_name: str) -> list[Any]:
          """Return messages for a specific worker."""
          with self._lock:
              return [msg for name, _, msg in self._messages if name == worker_name]
  ```

- [x] Add `message_log: MessageAccumulator` field to `RuntimeConfig`:
  ```python
  @dataclass(frozen=True, slots=True)
  class RuntimeConfig:
      cli_model: ModelType | None
      run_approval_policy: RunApprovalPolicy
      max_depth: int = 5
      on_event: EventCallback | None = None
      verbosity: int = 0
      usage: UsageCollector = field(default_factory=UsageCollector)
      message_log: MessageAccumulator = field(default_factory=MessageAccumulator)
  ```

- [x] Update `Worker.call()` to log messages to accumulator:
  ```python
  # After agent.run() completes:
  if result:
      config.message_log.extend(self.name, child_state.depth, result.all_messages())
  ```

- [x] Add `message_log` property to `WorkerRuntime` for convenience:
  ```python
  @property
  def message_log(self) -> list[tuple[str, int, Any]]:
      return self.config.message_log.all()
  ```

- [x] Keep `CallFrame.messages` unchanged - it's working correctly for conversation context

- [x] Keep `_should_use_message_history()` unchanged - it correctly gates multi-turn behavior

## Verification

```bash
uv run pytest tests/runtime/ -v
uv run pytest tests/ -k message -v
```

Test that accumulator captures all messages:
```python
# After a run with nested workers:
log = ctx.message_log
parent_msgs = [m for name, _, m in log if name == "parent"]
child_msgs = [m for name, _, m in log if name == "child"]

# Parent sees tool call/result in its conversation
assert any(has_tool_call(m) for m in parent_msgs)

# Accumulator captured child's internal messages too
assert len(child_msgs) > 0

# But parent's CallFrame.messages doesn't include child's internals
assert "child instructions" not in str(ctx.messages)
```

## Risks / Edge Cases

- Thread safety: Use lock like `UsageCollector`
- Memory: For long runs, accumulator could grow large - consider optional flag to disable
- Performance: Copying messages has overhead - only enable when needed?

## Notes

- This is now a simpler addition rather than a refactoring
- `CallFrame.messages` stays as-is (current isolation is correct)
- Phase 3 (Immutable CallState) may still be possible since `CallFrame.messages` is per-worker, not shared
- Consider: should `message_log` be optional/disabled by default for production?
