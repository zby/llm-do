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

### 3. Per-worker toolset configuration
Are per-worker toolset overrides or configs expected to grow in importance?

**Current state:**
- Not supported - toolsets in worker files are just names (`list[str]`)
- The `dict[str, dict]` → `list[str]` simplification removed this flexibility intentionally
- If toolset config is needed, users define a Python toolset instance

Is this sufficient long-term, or will we need per-worker config (e.g., different shell rules per worker)?
