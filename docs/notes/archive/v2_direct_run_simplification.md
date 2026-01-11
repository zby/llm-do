# Simplifying v2_direct run.py

## Status
Updated to reflect the current runtime architecture with `InvocableRegistry` and entry-name execution.

## Context
`experiments/inv/v2_direct/run.py` demonstrates running workers directly from Python. This note tracks how to reduce boilerplate without obscuring runtime/approval boundaries.

## Findings
- `InvocableRegistry` is now the symbol table; `build_invocable_registry(...)` resolves `.worker` + `.py` entries and handles two-pass wiring.
- `Runtime.run_entry()` (and `run_entry_sync()`) is the preferred entry-name execution path; `run_invocable()` remains a lower-level escape hatch.
- Approvals are still applied per worker call via `wrap_toolsets_for_approval` inside `Worker.call`.
- `v2_direct` is simplified by building a registry once and running by entry name; boilerplate is now mostly instruction loading and explicit worker/toolset wiring.
- `base_path` duplication for attachments vs filesystem toolsets remains a known annoyance.

## Open Questions
- Should `v2_direct` move to `.worker` files + registry builder to align with CLI/project workflows?
- Is the `base_path` duplication a real pain point worth solving at the runtime/toolset boundary?
- Do we want a builder that accepts `WorkerDefinition` constants (so scripts can avoid file parsing and two-pass wiring)?

## Conclusion
Registry-based entry execution is the current direction. Further simplification should focus on definition-level builders or path resolution cleanup.
