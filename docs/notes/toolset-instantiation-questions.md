# Toolset Instantiation Questions

## Context
Remaining open questions from toolset resolution review (extracted from archived `toolset-resolution-placement.md`).

## Open Questions

### 1. Per-worker vs shared toolset instances
Should toolsets be instantiated per worker or shared across workers?

**Current state:**
- Builtins: instantiated per-worker (based on `worker_root`)
- Python toolsets: shared across workers
- WorkerToolsets: wrap shared Worker stubs

This is inconsistent. Is that intentional or should we pick one model?

### 2. Entry/toolset namespace separation
How should entry names and toolset names be separated if they share a registry?

**Current state:**
- Workers become toolsets via `WorkerToolset` wrapper
- Entry names and toolset names share the same namespace
- No explicit separation mechanism

Is this a problem? Could cause confusion if a Python toolset has the same name as a worker.

### 3. Per-worker toolset configuration (**RESOLVED**)

**Update (2026-01):** This question is resolved. The architecture now uses `ToolsetSpec` with a factory pattern:

```python
# Worker now has:
toolset_specs: list[ToolsetSpec]

# ToolsetSpec wraps a factory:
@dataclass(frozen=True, slots=True)
class ToolsetSpec:
    factory: ToolsetFactory  # Callable[[ToolsetBuildContext], AbstractToolset]
```

Per-worker configuration is supported through the factory pattern - each `ToolsetSpec` can capture configuration in its factory closure. Worker files can specify toolsets by name (resolved via `ToolsetBuildContext.available_toolsets`), while programmatic `Worker` construction can pass fully configured `ToolsetSpec` instances directly.
