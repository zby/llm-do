# Invocable Wrapping Mental Model

## Context
Current worker tooling allows the same Python callable to be wrapped by multiple workers, each adding distinct approval policies. Because the wrapper preserves the original tool schema (including the name), the LLM sees identical tools even though runtime behavior differs by wrapper. Toolsets may also be wrapped multiple times and unwrapped to rebuild final tool lists. This makes it easy to overlook that one underlying function is represented by many wrapped variants and creates brittle assumptions about when wrappers are applied.

## Findings
- **Global pre-wrapped registry beats recursive wrapping.** Instead of passing wrapped toolsets into wrappers (and then unwrapping to avoid double-wrapping), keep a global registry of base invocables and produce per-worker wrapped versions on demand. Workers would select their invocables from the registry and wrap them once when constructing their exposed tool list.
- **Worker identity becomes the wrapper input.** The wrapper would take a worker identifier (or policy bundle) and the base invocable, returning a worker-specific invocable with approval and logging baked in. The same schema can exist in multiple worker contexts without ambiguity because the worker is part of the creation path, not the runtime tool schema.
- **Separation of concerns for approval.** Approval policies stay attached to workers, not to shared toolsets. Shared libraries expose bare invocables; workers inject approval, auditing, or instrumentation at wrap time. This prevents “approval leakage” when tools are reused by different workers.
- **Deterministic tool assembly.** Building a worker’s tool list becomes a pure operation: start from base invocables, wrap each with the worker’s policy, and present the resulting schemas. No stateful unwrapping or mutation of shared collections is needed, reducing ordering bugs.
- **Clearer mental model for LLM calls.** Each tool call is still dispatched via a worker, but the ambiguity of “which wrapper produced this schema?” disappears. Developers know the tool schema is identical, yet the worker that exposed it determines the approval path.

## Open Questions
- How should the global registry be defined—static module export, dependency-injected list, or discovery via entry points? Simpler is better but we should balance testability with ergonomics.
- Should wrapped invocables encode worker metadata (e.g., `__wrapped_worker__`) for debugging and logging, or is the worker name in the call context sufficient?
- Do any existing flows rely on cross-worker sharing of already-wrapped invocables (e.g., to preserve instrumentation)? If so, what compatibility shim is needed during migration?

## Conclusion
Adopting a global base-invocables registry with per-worker wrapping simplifies the mental model: tools are defined once, workers add their policies at assembly time, and the LLM sees consistent schemas even when runtime behavior differs per worker. Further design should prototype the registry interface and confirm no current flows depend on nested wrapping.
