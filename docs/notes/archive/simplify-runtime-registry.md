# Simplify runtime/registry.py

## Context
Review of `llm_do/runtime/registry.py` and its local imports to identify simplification opportunities in registry construction and tool/worker resolution.

## Findings

### 1) Remove redundant conflict check for Python entries (redundant validation)
`load_all_from_files()` already rejects name conflicts between Python workers and `@entry` functions. The extra guard when adding `python_entries` to `entries` should never fire and can be removed to reduce noise.

### 2) Drop the extra `workers` mapping (duplicated derived values)
`worker_entries` already holds the same stub objects updated in the second pass. Instead of populating `workers` and then `entries.update(workers)`, update `entries` directly from `worker_entries` after they are filled.

### 3) Avoid reassigning stub fields that were already set (duplicated derived values)
Stubs are created with `instructions`, `description`, and `model` from `worker_def`, then those same fields are written again in the second pass. Either:
- Create stubs with only `name` + placeholder `instructions` and fill once in the second pass, or
- Keep the current stub creation and skip reassigning `instructions`/`description` (only set fields that can change, like model override, schema/toolsets).

### 4) Consolidate per-worker bookkeeping (over-specified interface)
The trio of `worker_entries`, `worker_paths`, and `worker_defs` can drift if keyed incorrectly. A small dataclass (e.g., `WorkerSpec {name, path, definition, stub}`) would reduce repeated lookups and make the two-pass flow easier to follow.

### 5) Lazily build global toolset map for entry functions (unused flexibility)
`global_builtins`/`all_available_toolsets` are only used to resolve `EntryFunction.toolset_refs`. If there are no entry functions (or none with toolset refs), skip building this map.

## Open Questions
- Should we keep the two-pass structure but fold the maps into a single `WorkerSpec` type, or keep the current maps for explicitness?
- Is it worth making stub construction “minimal” to avoid any duplicated assignment, or is the current clarity worth the minor redundancy?

## Conclusion
The registry logic is already clean; the remaining simplifications are mostly about reducing redundant maps and writes, and trimming checks that can never trigger due to upstream validation.
