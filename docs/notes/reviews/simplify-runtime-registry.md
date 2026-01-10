# Simplify runtime/registry.py

## Context
Review of `llm_do/runtime/registry.py` and its local imports (`llm_do/runtime/discovery.py`, `llm_do/runtime/worker_file.py`, `llm_do/toolsets/loader.py`, `llm_do/toolsets/builtins.py`, `llm_do/runtime/schema_refs.py`) to identify simplification opportunities in registry construction and tool/worker resolution.

## Findings

### 1) Avoid double parsing of worker files (duplicated derived values)
Current code (two passes read the same file):
```python
for worker_path in worker_files:
    worker_file = load_worker_file(worker_path)
    ...

for name, worker_path in worker_paths.items():
    overrides = set_overrides if name == entry_name else None
    worker_file = load_worker_file(worker_path, overrides=overrides)
    ...
```
Proposed simplification:
- Parse each worker file once, store the `WorkerDefinition` in a dict keyed by path/name.
- Apply overrides at parse time for the entry worker (or reparse only that one if needed).

Judgment call: this assumes `--set` overrides should affect the same definition used for stub creation. If overrides can change `name`, the current two-pass approach can create a mismatch (stub keyed by original name, second pass keyed by overridden name). A single cached definition prevents that inconsistency.

Inconsistency prevented: yes — avoids applying overrides only in the second pass while stubs and lookup keys were created from the unmodified definition.

### 2) Workers are discovered twice via toolsets + workers (unused flexibility, redundant mapping)
Discovery returns `Worker` instances both as toolsets and as workers because `Worker` is an `AbstractToolset`:
```python
module_toolsets = discover_toolsets_from_module(module)
module_workers = discover_workers_from_module(module)
```
Registry then special-cases `Worker` in `_get_tool_names()` and relies on the “already in entries” check to avoid duplication.

Proposed simplification:
- Exclude `Worker` instances from toolset discovery, then explicitly inject `python_workers` into `available_toolsets` keyed by `worker.name`.
- Remove the `Worker` branch from `_get_tool_names()` and reduce ambiguity between “attribute name” vs “worker.name”.

Judgment call: this drops the ability to reference Python workers by their module attribute name if it differs from `worker.name`. If that flexibility is needed, keep the current behavior.

Inconsistency prevented: yes — today a worker can be referenced by attribute name in toolsets resolution but appears under `worker.name` in entries; this makes the naming model consistent.

### 3) Async registry builder without async work (unused flexibility)
`build_invocable_registry()` is async purely because `_get_tool_names()` is async, but `_get_tool_names()` doesn’t await:
```python
async def _get_tool_names(...):
    ...
    return []

async def build_invocable_registry(...):
    tool_names = await _get_tool_names(toolset)
```
Proposed simplification:
- Make `_get_tool_names()` synchronous and remove `await`.
- Consider making `build_invocable_registry()` synchronous as well, since nothing inside actually awaits.

Judgment call: if you plan to support toolset introspection that truly needs async (e.g., `get_tools(run_ctx)`), you may want to keep the async surface for future compatibility.

Inconsistency prevented: no direct bug, but removes misleading async APIs that imply I/O where none exists.

### 4) Repeated path resolution (duplicated derived values)
Within the worker loop, `Path(worker_path).resolve()` is called multiple times (worker root, schema resolution base path, toolset context).

Proposed simplification:
- Resolve once per worker (e.g., `resolved_path = Path(worker_path).resolve()`) and reuse.

Judgment call: low-risk cleanup.

Inconsistency prevented: no, but reduces repeated computation and clarifies data flow.

## Open Questions
- Should Python workers be referenceable by module attribute name, or strictly by `worker.name`?
- Is it acceptable to remove async from registry building to simplify the API, or do we expect async toolset introspection soon?

## Conclusion
Decision so far: skip caching built-in toolsets to keep registry construction simple. Other items remain open.
