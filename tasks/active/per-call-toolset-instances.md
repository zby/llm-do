# Per-Call Toolset Instances

## Status
active

## Problem

Toolsets are currently instantiated **per-entry-build**, not **per-call**. This breaks isolation for recursive worker calls.

If Worker A calls itself:
```
Worker A (call 1)
  └── Worker A (call 2)  ← shares same toolset instances as call 1
```

Both invocations share the same `self.toolsets` list, so handles/state leak between recursive calls.

## Decisions

### 1. Worker API - Specs vs Instances
**Decision: Keep both fields (backwards compatible)**

- Add `toolset_specs: list[ToolsetSpec]` for per-call instantiation
- Keep `toolsets: list[AbstractToolset]` for shared/legacy instances
- If `toolset_specs` is set, use it; otherwise fall back to `toolsets`

### 2. Where instantiation happens
**Decision: Worker._call_internal**

Worker already has access to `self.toolset_specs` and is the natural place to instantiate before wrapping for approval.

### 3. Where cleanup happens
**Decision: Local finally block in Worker._call_internal**

```python
async def _call_internal(self, ...):
    # Instantiate from specs if available
    if self.toolset_specs:
        toolsets = [spec.factory(ctx) for spec in self.toolset_specs]
    else:
        toolsets = self.toolsets or []

    try:
        wrapped = wrap_toolsets_for_approval(toolsets, ...)
        # ... run agent ...
        return output
    finally:
        if self.toolset_specs:  # only cleanup if we created them
            await self._cleanup_toolsets(toolsets)
```

Simple, self-contained, cleanup always runs even on error.

## Tasks

- [ ] Add `toolset_specs: list[ToolsetSpec]` field to Worker dataclass
- [ ] Update `Worker._call_internal` to instantiate from specs
- [ ] Add cleanup in finally block (extract helper from Runtime._cleanup_toolsets)
- [ ] Remove cleanup from `Runtime.run_entry()` (or keep for `toolsets` path only)
- [ ] Update registry to populate `toolset_specs` instead of `toolsets` for worker files
- [ ] Update tests to verify per-call isolation
- [ ] Add test for recursive worker with stateful toolset

## Files to Modify

- `llm_do/runtime/worker.py` - Add field, instantiation, cleanup
- `llm_do/runtime/shared.py` - Adjust/remove entry-level cleanup
- `llm_do/runtime/registry.py` - Populate toolset_specs
- `llm_do/toolsets/loader.py` - May need adjustments

## Migration

Existing code using `Worker(toolsets=[...])` continues to work (shared instances, no per-call isolation). New code should use `Worker(toolset_specs=[...])` for proper isolation.

## Related

- Completed: `tasks/completed/113-per-worker-toolset-instances.md` (original per-worker work)
- SOLID review: `docs/notes/reviews/review-solid.md`
