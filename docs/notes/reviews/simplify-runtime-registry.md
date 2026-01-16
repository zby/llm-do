# Simplify runtime/registry.py

## Context
Simplification review of `llm_do/runtime/registry.py` plus its internal
dependencies (`llm_do/toolsets/*`, `llm_do/runtime/worker.py`,
`llm_do/runtime/worker_file.py`, `llm_do/runtime/discovery.py`,
`llm_do/runtime/schema_refs.py`, `llm_do/runtime/args.py`,
`llm_do/runtime/contracts.py`, and `llm_do/config.py`) to reduce duplicate
registry wiring and tighten entry/toolset linking rules.

## Findings
- **Worker toolset spec helper duplicates `Worker.as_toolset_spec()`**
  - Pattern: duplicated derived values / over-specified interface.
  - Registry defines `_worker_toolset_spec()` to wrap a `Worker` in
    `WorkerToolset`, but `Worker.as_toolset_spec()` already centralizes this.
  - Simplify by building `available_workers` via
    `spec.stub.as_toolset_spec()` and delete the helper.
  - Tradeoff: none; it keeps worker toolset creation in one place if approval
    config behavior evolves.

- **`EntryFunction.toolset_context` is assigned twice**
  - Pattern: redundant derived values.
  - `EntryFunction.resolve_toolsets()` already sets `toolset_context`, but
    registry reassigns it immediately after calling `resolve_toolsets()`.
  - Simplify by removing the extra assignment.

- **Entry/name validation is duplicated across registry and worker parsing**
  - Pattern: redundant validation.
  - Registry validates `name` and `entry` from raw frontmatter, then
    `build_worker_definition()` validates the same fields again.
  - Simplify by parsing a `WorkerDefinition` first (no overrides), using
    `worker_def.name` / `worker_def.entry` for conflict checks, and only
    re-parsing with overrides for the entry worker if needed.
  - Alternative: expose a shared `parse_entry` helper from `worker_file`.
  - Tradeoff: slightly more control flow, but removes duplication and keeps
    entry parsing rules in one place.

- **`_merge_toolsets()` allows identical-object duplicates**
  - Pattern: unused flexibility.
  - Current behavior only errors if the duplicate name maps to a different
    object, but call sites never merge the same object from multiple sources.
  - Simplify by always raising on duplicate keys to make conflicts explicit.
  - Tradeoff: loses the (currently unused) ability to pass the same mapping
    twice without error.

- **`entries` is built incrementally for conflict checks**
  - Pattern: duplicated derived values.
  - The dict is assembled early just to check `.worker` name conflicts, then
    rebuilt again with worker stubs.
  - Simplify by tracking a `reserved_names` set for conflict checks and
    constructing the final `entries` dict once at the end.
  - Tradeoff: a small refactor, but the flow reads more linearly.

## Open Questions
- Do we ever want duplicate toolset names across sources to be allowed if they
  are the same `ToolsetSpec` instance, or should duplicates always be errors?
- Is the "overrides only apply to entry worker" rule permanent? If it is, the
  parse-once + optional rebuild approach stays clean; if not, entry selection
  needs a different mechanism.

## Conclusion
`runtime/registry.py` is mostly lean. The biggest simplifications are removing
duplicate worker-toolset wiring, eliminating redundant `toolset_context`
assignment, and collapsing repeated frontmatter validation into a single parse
path. Tightening `_merge_toolsets()` and deferring `entries` assembly are
secondary cleanups that clarify intent without changing behavior.
