---
description: Open questions on per-worker vs shared toolset instances
---

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

**Update (2026-02):** This question is resolved. The architecture now uses `ToolsetDef`
with explicit `TOOLSETS` registries and `ToolsetFunc` factories:

```python
# Agent now has:
toolsets: list[ToolsetDef]

# ToolsetDef is:
ToolsetDef = AbstractToolset[Any] | ToolsetFunc[Any]
```

Per-agent configuration is supported through the factory pattern - each
`ToolsetFunc` can capture configuration in its closure. `.agent` files specify
toolsets by name (resolved via the TOOLSETS registry), while programmatic
`AgentSpec` construction can pass fully configured ToolsetDef entries directly.
