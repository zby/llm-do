# Immutable CallConfig

## Status
backlog

## Prerequisites
- [x] Two-Object API task completed
- [x] Extract MessageAccumulator task completed

## Goal
Separate CallFrame into immutable configuration (`CallConfig`) and mutable state, making the boundaries explicit and enforced.

**Important constraint discovered in Phase 2:**
Messages MUST stay in CallFrame for correct worker isolation:
- Each worker has its own `messages` list
- Parent workers don't see child workers' internal messages
- Only tool call/result is visible to parent
- Multi-turn conversations accumulate at entry level (depth ≤ 1)

## Design

Split CallFrame into two parts:

```python
@dataclass(frozen=True, slots=True)
class CallConfig:
    """Immutable call configuration - set at fork time, never changed."""
    toolsets: tuple[AbstractToolset[Any], ...]
    model: ModelType
    depth: int = 0


@dataclass(slots=True)
class CallFrame:
    """Per-worker call state with immutable config and mutable conversation state."""
    config: CallConfig

    # Mutable fields (required for runtime behavior)
    prompt: str = ""
    messages: list[Any] = field(default_factory=list)

    # Convenience accessors for backward compatibility
    @property
    def toolsets(self) -> tuple[AbstractToolset[Any], ...]:
        return self.config.toolsets

    @property
    def model(self) -> ModelType:
        return self.config.model

    @property
    def depth(self) -> int:
        return self.config.depth

    def fork(
        self,
        toolsets: Sequence[AbstractToolset[Any]] | None = None,
        *,
        model: ModelType | None = None,
    ) -> CallFrame:
        """Create child frame with incremented depth and fresh messages."""
        new_config = CallConfig(
            toolsets=tuple(toolsets) if toolsets is not None else self.config.toolsets,
            model=model if model is not None else self.config.model,
            depth=self.config.depth + 1,
        )
        return CallFrame(config=new_config)
```

## Rationale

### Why this design?

1. **Explicit immutability boundary** - `CallConfig` is frozen, enforced by Python
2. **Clear semantics**:
   - `CallConfig` = "what this worker is" (toolsets, model, depth)
   - `CallFrame` mutable fields = "conversation state" (messages, prompt)
3. **Type safety** - can't accidentally mutate config fields
4. **Testability** - can compare `CallConfig` instances directly

### Why messages must stay mutable

Verified behavior (see Phase 2 verification):
```
Parent Worker (depth 1):
  messages = [UserPrompt, ToolCall(child), ToolResult, Response]
                         ↑ only sees this, not child's internal messages

Child Worker (depth 2):
  messages = [UserPrompt, Response]  ← isolated, discarded after return
```

The mutation pattern `state.messages[:] = ...` is required for multi-turn conversations.

## Context

- Relevant files:
  - `llm_do/runtime/context.py` - `CallFrame` definition
  - `llm_do/runtime/worker.py` - uses `state.fork()`, `state.messages`
  - `llm_do/runtime/contracts.py` - may need updates

- Current mutation points:
  ```python
  # These stay (mutable state):
  state.messages[:] = list(child_state.messages)
  runtime.messages[:] = _get_all_messages(result)
  self.frame.prompt = value

  # These would be eliminated (now in frozen CallConfig):
  # (none currently - toolsets/model/depth aren't mutated)
  ```

## Tasks

- [ ] Add `CallConfig` frozen dataclass to `context.py`:
  ```python
  @dataclass(frozen=True, slots=True)
  class CallConfig:
      toolsets: tuple[AbstractToolset[Any], ...]
      model: ModelType
      depth: int = 0
  ```

- [ ] Update `CallFrame` to contain `CallConfig`:
  ```python
  @dataclass(slots=True)
  class CallFrame:
      config: CallConfig
      prompt: str = ""
      messages: list[Any] = field(default_factory=list)

      @property
      def toolsets(self) -> tuple[...]: return self.config.toolsets
      @property
      def model(self) -> ModelType: return self.config.model
      @property
      def depth(self) -> int: return self.config.depth
  ```

- [ ] Update `fork()` to create new `CallConfig`

- [ ] Update `clone_same_depth()` similarly

- [ ] Update `WorkerRuntime.__init__` to create `CallConfig` and wrap in `CallFrame`

- [ ] Update `WorkerRuntime.from_entry()` similarly

- [ ] Search for any code accessing `frame.toolsets` etc. (should work via properties)

- [ ] Run tests to verify backward compatibility

## Verification

```bash
uv run pytest tests/runtime/ -v
uv run pytest tests/ -v
```

Verify immutability:
```python
frame = CallFrame(config=CallConfig(toolsets=(), model="test", depth=0))

# This should raise FrozenInstanceError
frame.config.depth = 1  # ✗ fails

# This should work
assert frame.depth == 0
assert frame.config.depth == 0

# Mutable state still works
frame.messages.append(msg)  # ✓ works
frame.prompt = "new"        # ✓ works
```

Verify messages still work:
```python
ctx = WorkerRuntime.from_entry(worker)
await ctx.run(worker, {"input": "turn 1"})
await ctx.run(worker, {"input": "turn 2"})
assert len(ctx.messages) > 2  # accumulated
```

## Risks / Edge Cases

- **API change**: Code accessing `frame.toolsets` directly works (via property)
- **Code accessing `frame.config`**: New API, callers need update
- **Backward compatibility**: `toolsets` changes from list to tuple
- **Complexity**: Nested structure adds indirection

## Notes

- This is Phase 3 of a 3-phase refactoring:
  - Phase 1: Two-Object API ✓
  - Phase 2: Extract MessageAccumulator ✓ (diagnostic sink)
  - Phase 3: Immutable CallConfig (this task)

- Full CallFrame immutability is NOT possible due to message isolation requirements
- The `MessageAccumulator` captures all messages for diagnostics, but workers read from `CallFrame.messages` for conversation context

- After this phase, mutable containers in runtime:
  - `UsageCollector` - intentionally mutable, thread-safe
  - `MessageAccumulator` - intentionally mutable, thread-safe
  - `CallFrame.messages` - required for correct isolation
  - `CallFrame.prompt` - set once per run
