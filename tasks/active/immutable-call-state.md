# Immutable CallState (CallFrame)

## Status
backlog

## Prerequisites
- [ ] Two-Object API task completed (`tasks/backlog/two-object-api.md`)
- [ ] Extract MessageAccumulator task completed (`tasks/backlog/extract-message-accumulator.md`)

## Goal
Make `CallFrame` (consider renaming to `CallState`) a frozen dataclass with functional update methods, enabling clear data flow and thread-safety by construction.

**Before:**
```python
@dataclass(slots=True)
class CallFrame:
    toolsets: list[AbstractToolset[Any]]
    model: ModelType
    depth: int = 0
    prompt: str = ""

    def fork(self, toolsets=None, *, model=None) -> CallFrame:
        return CallFrame(
            toolsets=self.toolsets if toolsets is None else toolsets,
            model=self.model if model is None else model,
            depth=self.depth + 1,
            prompt=self.prompt,
        )
```

**After:**
```python
@dataclass(frozen=True, slots=True)
class CallState:
    toolsets: tuple[AbstractToolset[Any], ...]  # immutable tuple
    model: ModelType
    depth: int = 0
    prompt: str = ""

    def with_incremented_depth(self) -> CallState:
        return replace(self, depth=self.depth + 1)

    def with_depth(self, depth: int) -> CallState:
        return replace(self, depth=depth)

    def with_toolsets(self, toolsets: Sequence[AbstractToolset[Any]]) -> CallState:
        return replace(self, toolsets=tuple(toolsets))

    def with_model(self, model: ModelType) -> CallState:
        return replace(self, model=model)

    def with_prompt(self, prompt: str) -> CallState:
        return replace(self, prompt=prompt)

    def fork(
        self,
        toolsets: Sequence[AbstractToolset[Any]] | None = None,
        *,
        model: ModelType | None = None,
    ) -> CallState:
        """Create a child state with incremented depth."""
        return CallState(
            toolsets=tuple(toolsets) if toolsets is not None else self.toolsets,
            model=model if model is not None else self.model,
            depth=self.depth + 1,
            prompt=self.prompt,
        )
```

## Rationale

With messages moved to `RuntimeConfig` (Phase 2), `CallFrame` no longer has shared mutable state. Making it frozen provides:

1. **Clear data flow** - no hidden mutation, easy to trace state changes
2. **Thread-safety by construction** - frozen dataclasses are inherently safe
3. **Easy testing** - can compare before/after states directly
4. **Functional style** - `with_*` methods return new instances

## Context

- Relevant files:
  - `llm_do/runtime/context.py` - `CallFrame` definition, `WorkerRuntime`
  - `llm_do/runtime/worker.py` - uses `state.fork()` in `Worker.call()`
  - `llm_do/runtime/contracts.py` - may need protocol updates

- Current `CallFrame` methods:
  ```python
  def fork(self, toolsets=None, *, model=None) -> CallFrame:
      """Create child frame with depth+1."""

  def clone_same_depth(self, toolsets=None, *, model=None) -> CallFrame:
      """Create copy without changing depth."""
  ```

- Current mutation points (should be eliminated after Phase 2):
  ```python
  self.frame.prompt = value  # via WorkerRuntime.prompt setter
  ```

## Tasks

- [ ] Rename `CallFrame` to `CallState` (optional but recommended for clarity):
  - Update class name in `context.py`
  - Update all references in `context.py`, `worker.py`, `contracts.py`
  - Update type hints throughout

- [ ] Change `toolsets` from `list` to `tuple`:
  ```python
  toolsets: tuple[AbstractToolset[Any], ...]
  ```

- [ ] Make dataclass frozen:
  ```python
  @dataclass(frozen=True, slots=True)
  class CallState:
      ...
  ```

- [ ] Add `with_*` methods for functional updates:
  ```python
  from dataclasses import replace

  def with_depth(self, depth: int) -> CallState:
      return replace(self, depth=depth)

  def with_incremented_depth(self) -> CallState:
      return replace(self, depth=self.depth + 1)

  def with_toolsets(self, toolsets: Sequence[AbstractToolset[Any]]) -> CallState:
      return replace(self, toolsets=tuple(toolsets))

  def with_model(self, model: ModelType) -> CallState:
      return replace(self, model=model)

  def with_prompt(self, prompt: str) -> CallState:
      return replace(self, prompt=prompt)
  ```

- [ ] Update `fork()` method to use immutable patterns:
  ```python
  def fork(
      self,
      toolsets: Sequence[AbstractToolset[Any]] | None = None,
      *,
      model: ModelType | None = None,
  ) -> CallState:
      return CallState(
          toolsets=tuple(toolsets) if toolsets is not None else self.toolsets,
          model=model if model is not None else self.model,
          depth=self.depth + 1,
          prompt=self.prompt,
      )
  ```

- [ ] Update or remove `clone_same_depth()`:
  - Option A: Keep as convenience method using `replace()`
  - Option B: Remove, callers use `with_*` methods directly
  ```python
  def clone_same_depth(
      self,
      toolsets: Sequence[AbstractToolset[Any]] | None = None,
      *,
      model: ModelType | None = None,
  ) -> CallState:
      return CallState(
          toolsets=tuple(toolsets) if toolsets is not None else self.toolsets,
          model=model if model is not None else self.model,
          depth=self.depth,  # same depth
          prompt=self.prompt,
      )
  ```

- [ ] Update `WorkerRuntime.prompt` setter:
  - Current: `self.frame.prompt = value` (mutation)
  - After: Must replace the frame
  ```python
  @prompt.setter
  def prompt(self, value: str) -> None:
      self.frame = self.frame.with_prompt(value)
  ```
  - This requires `WorkerRuntime.frame` to NOT be a frozen field
  - Or: Remove the setter, require explicit state threading

- [ ] Update `WorkerRuntime.__init__` to convert list toolsets to tuple:
  ```python
  frame = CallState(
      toolsets=tuple(toolsets),
      ...
  )
  ```

- [ ] Update `WorkerRuntime.from_entry()` similarly

- [ ] Update `Worker.call()` to work with immutable state:
  - Current: `child_runtime = runtime.spawn_child(...)`
  - Should work unchanged if `spawn_child` returns new `WorkerRuntime` with forked state

- [ ] Search for any remaining mutation patterns:
  ```bash
  grep -r "\.frame\." llm_do/runtime/
  grep -r "frame\." llm_do/runtime/ | grep "="
  ```

## Verification

```bash
uv run pytest tests/runtime/ -v
uv run pytest tests/ -v
```

Verify immutability:
```python
# This should raise FrozenInstanceError
state = CallState(toolsets=(), model="test", depth=0, prompt="")
state.depth = 1  # Should fail

# This should work
new_state = state.with_depth(1)
assert new_state.depth == 1
assert state.depth == 0  # original unchanged
```

## Risks / Edge Cases

- **prompt setter**: `WorkerRuntime.prompt = value` currently mutates frame. Need to decide:
  - Option A: Replace frame reference (WorkerRuntime.frame becomes mutable attribute)
  - Option B: Remove setter, require explicit state management
  - Option C: Keep prompt in RuntimeConfig (it's set once per run anyway)

- **Toolset tuple conversion**: Ensure all callers pass sequences, not generators

- **Performance**: `replace()` creates new objects - should be negligible but verify

- **Backward compatibility**: Any code directly accessing `frame.toolsets` and expecting a list will break

## Notes

- This is Phase 3 of a 3-phase refactoring:
  - Phase 1: Two-Object API
  - Phase 2: Extract MessageAccumulator
  - Phase 3: Immutable CallState (this task)

- Consider also renaming `RuntimeConfig` to `RunConfig` for consistency:
  - `RunConfig` - "the run" (global, immutable, shared)
  - `CallState` - "the call" (per-worker, now also immutable)

- After this phase, the only mutable containers in the runtime are:
  - `UsageCollector` - intentionally mutable, thread-safe
  - `MessageAccumulator` - intentionally mutable, thread-safe
  - `WorkerRuntime.frame` reference - may need to be reassignable for prompt setter

- The functional `with_*` pattern is idiomatic Python for immutable updates (see `dataclasses.replace`, `typing.NamedTuple`, etc.)
