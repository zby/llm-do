# Toolset Resolution Placement

## Context
We want a clearer mental model for the runtime and considered describing
`InvocableRegistry` as a symbol table. A follow-up question is whether toolset
resolution should live in the same place to simplify the architecture.

## Findings
- `InvocableRegistry` is a flat entry symbol table: name -> resolved invocable
  (workers + tool-backed entries).
- Toolset names are scoped per worker. Builtins depend on worker path, and a
  worker cannot include itself as a toolset; this makes a single global toolset
  table misleading without extra indirection.
- The current two-pass build is effectively a linker: first declare worker
  symbols, then resolve toolset references using the worker's scope.
- A unified "Resolver" could return two artifacts: a global entry table and
  per-worker toolset bindings, keeping scope explicit while centralizing name
  resolution.
- Deferring toolset resolution to runtime would simplify build-time wiring but
  shifts failures to execution and may instantiate toolsets multiple times.

## Open Questions
- Should toolsets be instantiated per worker or shared across workers?
- Do we want resolution failures at build time or at call time?
- How should entry names and toolset names be separated if a single registry
  object owns both?
- Are per-worker toolset overrides or configs expected to grow in importance?
