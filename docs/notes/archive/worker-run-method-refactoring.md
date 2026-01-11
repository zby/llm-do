# Worker.run() Method Refactoring

## Context
Discussion about moving the `run()` functionality from a standalone function to a method on `Worker`.

## Current Design

```
cli/main.py::run(files, prompt, ...)
    → build_entry(files) → Invocable
    → run_invocable(invocable, prompt, approval_policy, ...)
        → WorkerRuntime.from_entry(invocable, ...)
        → ctx.run(invocable, input_data)
```

Problems:
- `run()` in cli/main.py mixes file parsing with execution
- Tests need to monkey-patch `build_entry` to inject test models
- Added `entry` parameter for DI, but this is a half-measure

## Proposed Design

Add `run()` method directly on `Worker`:

```python
class Worker:
    async def run(
        self,
        prompt: str,
        *,
        model: str | None = None,
        approval_policy: RunApprovalPolicy,
        on_event: EventCallback | None = None,
        verbosity: int = 0,
        message_history: list[ModelMessage] | None = None,
    ) -> tuple[Any, WorkerRuntime]:
        """High-level run API for CLI and programmatic use."""
        ctx = WorkerRuntime.from_entry(
            self,
            model=model,
            run_approval_policy=approval_policy,
            messages=list(message_history) if message_history else None,
            on_event=on_event,
            verbosity=verbosity,
        )
        input_data = {"input": prompt}
        if on_event:
            on_event(UserMessageEvent(worker=self.name, content=prompt))
        result = await ctx.run(self, input_data)
        return result, ctx
```

## Benefits

1. **Cleaner API**: `worker.run(prompt)` instead of `run_invocable(worker, prompt)`
2. **Better separation**: CLI handles file parsing, Worker handles execution
3. **Easier testing**: No monkey-patching needed, just create Worker and call `.run()`
4. **Discoverable**: Method on the object you're working with

## CLI Changes

Before:
```python
result, ctx = await run(files=[...], prompt=..., ...)
```

After:
```python
worker = await build_entry(files, ...)
result, ctx = await worker.run(prompt, approval_policy=..., ...)
```

## Why Only on Worker (not Invocable Protocol)

- `Worker` is the main CLI entry point
- `ToolInvocable` is called programmatically via `ctx.call()`, not directly run
- Keeps `Invocable` protocol minimal (just `name` + `call()`)
- Runtime setup (approval, events) is Worker-specific concern

## Implementation Steps

1. Add `run()` method to `Worker` class in `llm_do/runtime/worker.py`
2. Update `llm_do/cli/main.py` to call `build_entry()` first, then `worker.run()`
3. Simplify or remove standalone `run()` function (or keep as convenience wrapper)
4. Update tests to use `worker.run()` directly
5. Remove `run_invocable()` if no longer needed

## Open Questions

- Should `run_invocable()` remain for `ToolInvocable` use cases?
- Should CLI's `run()` become a thin wrapper that calls `build_entry()` + `worker.run()`?
