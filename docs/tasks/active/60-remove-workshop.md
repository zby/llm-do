# Remove Workshop Concept

## Goal

Remove the workshop abstraction entirely. Workers are invoked directly, workers are resolved via a search path.

## Background

Workshop was solving several problems awkwardly:
- Entry point (`main.worker`) - but you can just call any worker directly
- Config inheritance - but per-worker config is cleaner
- Namespace - but that's just a directory

**Workers-as-tools is already implemented** (`AgentToolset` in `llm_do/agent_toolset.py`). This task focuses on:
1. Removing workshop machinery (`WorkshopContext`, `WorkshopConfig`, `workshop.yaml`)
2. Simplifying CLI invocation
3. Keeping the existing `toolsets:` system (it works well)

## What We're Keeping

### Toolsets System (unchanged)

The `toolsets:` configuration stays exactly as-is. It provides:
- Grouped tools with shared configuration (shell rules, filesystem paths, etc.)
- Clean alias system (`shell`, `filesystem`, `delegation`, `custom`)
- Expressive configuration (approval rules, allow_workers lists)
- Integration with the approval system

```yaml
# This syntax is NOT changing
toolsets:
  shell:
    rules:
      - pattern: "wc"
        approval_required: false
    default:
      approval_required: true
  delegation:
    allow_workers: ["helper", "summarizer"]
  custom:
    calculate_factorial: {}
```

### Direct Worker Invocation

```bash
# By name (searches workers/ directory)
llm-do code_reviewer "Review this PR"

# By explicit path
llm-do ./workers/orchestrator.worker "Do the thing"
llm-do ~/my-tools/summarizer.worker "Summarize this"
```

**No more directory invocation.** Previously you could call a directory and it would look for `main.worker`:
```bash
# OLD - no longer supported
llm-do ./my-workshop/
```

Now you always specify the worker explicitly:
```bash
# NEW - explicit worker
llm-do ./my-workshop/workers/orchestrator
```

### Directory Structure

```
my-project/
├── code_reviewer.worker       # simple form
├── summarizer.worker
├── orchestrator/              # directory form (for workers with local tools)
│   ├── worker.worker
│   └── tools.py               # local tools for this worker
└── tools.py                   # shared tools for all workers
```

Workers live at the project root (no `workers/` subdirectory). This ensures `tools.py` discovery works correctly.

## What Gets Removed

| Component | Status |
|-----------|--------|
| `InvocationMode.WORKSHOP` | Remove |
| `InvocationMode.SINGLE_FILE` | Keep (direct file path) |
| `InvocationMode.SEARCH_PATH` | Keep (worker name resolution) |
| `WorkshopContext` | Remove |
| `WorkshopConfig` | Remove |
| `llm_do/workshop.py` | Remove |
| `workshop.yaml` detection | Remove |
| `main.worker` special handling | Remove |
| `WorkerRegistry.workshop_config` | Remove |
| `_apply_workshop_config()` | Remove |

## What Changes

### WorkerRegistry

- Remove `workshop_config` parameter from constructor
- Remove `_apply_workshop_config()` method
- Remove workshop-level template search (keep worker-local templates)
- Remove workshop-level `tools.py` fallback for simple workers
- Update `_get_search_paths()`: remove `workers/` subdirectory, search root directly
- Update `find_custom_tools()`: search for `tools.py` at registry root for simple-form workers
- Update `list_workers()`: scan root instead of `workers/` subdirectory

### CLI

- Remove workshop detection logic from `resolve_workshop()`
- Simplify: argument is always a worker name or path
- Remove `--entry` flag (no workshop entry point concept)
- Remove `init workshop` command (or repurpose for project scaffolding)

### Worker Resolution

After removing workshop, resolution becomes:

1. **Explicit path**: `./path/to/worker.worker` or `./path/to/worker/`
2. **Name search**: Look in `workers/` directory of registry root

```python
def resolve_worker(arg: str, registry_root: Path) -> Path:
    """Resolve worker argument to a path."""
    path = Path(arg)

    # Explicit path (starts with ./ or /)
    if arg.startswith('./') or arg.startswith('/') or path.suffix == '.worker':
        return resolve_explicit_path(path, registry_root)

    # Name search in workers/ directory
    return search_workers_dir(arg, registry_root)
```

## Tasks

### Phase 1: Remove workshop from CLI

- [ ] Simplify `resolve_workshop()` to just path/name resolution
- [ ] Remove `InvocationMode.WORKSHOP` handling
- [ ] Remove `--entry` CLI flag
- [ ] Update CLI to not pass `workshop_config` to registry

### Phase 2: Remove workshop from registry

- [ ] Remove `workshop_config` parameter from `WorkerRegistry.__init__()`
- [ ] Remove `_apply_workshop_config()` method
- [ ] Remove workshop template directory from `_get_template_roots()`
- [ ] Remove workshop-level `tools.py` fallback from `find_custom_tools()`

### Phase 3: Remove workshop types and module

- [ ] Remove `WorkshopContext` from `types.py`
- [ ] Remove `WorkshopConfig` from `types.py`
- [ ] Remove `InvocationMode.WORKSHOP` from enum
- [ ] Delete `llm_do/workshop.py`
- [ ] Update imports in `llm_do/base.py`

### Phase 4: Update tests

- [ ] Remove/update `test_workshop.py` tests
- [ ] Update any integration tests using workshop mode
- [ ] Ensure worker resolution tests still pass

### Phase 5: Cleanup

- [ ] Remove `main.worker` special handling in search paths
- [ ] Update documentation
- [ ] Update examples (remove any `workshop.yaml` files, rename `main.worker` to meaningful names)

## Registry Root Determination

After removing workshop mode, registry root is determined by:

1. **Explicit `--registry` flag** (if provided)
2. **Current working directory** (default)

This is simple and predictable. The expected usage pattern:

```bash
# From project directory
cd examples/pitchdeck_eval
llm-do pitch_orchestrator "Evaluate all decks"

# Or with explicit registry
llm-do --registry ./examples/pitchdeck_eval pitch_orchestrator "Evaluate all decks"
```

Workers that delegate to other workers should be run from the project root (or with `--registry`), not by path.

## Migration

Existing workshops become regular directories:
- `main.worker` → delete (redundant with the actual orchestrator in `workers/`)
- `workshop.yaml` → delete (settings move to per-worker config)
- Workers keep their `toolsets:` configuration unchanged
- Update any scripts/docs that called the directory

```bash
# Before (directory invocation - looked for main.worker)
llm-do ./my-workshop/

# After (run from project directory)
cd my-workshop && llm-do orchestrator
```

### Example Cleanup: pitchdeck_eval

Current state:
```
examples/pitchdeck_eval/
├── main.worker                    # duplicate - DELETE
├── workers/
│   ├── pitch_orchestrator.worker
│   └── pitch_evaluator.worker
├── input/
└── evaluations/
```

After cleanup (flatten - no `workers/` subdirectory):
```
examples/pitchdeck_eval/
├── pitch_orchestrator.worker      # entry point
├── pitch_evaluator.worker
├── tools.py                       # if needed - discovered at same level
├── input/
└── evaluations/
```

Invocation:
```bash
cd examples/pitchdeck_eval
llm-do pitch_orchestrator "Evaluate all decks"
```

### Why Flatten?

The `workers/` subdirectory convention made sense with workshops (registry root was the workshop directory). Without workshops:

1. **Custom tools discovery**: `find_custom_tools()` looks for `tools.py` in the worker's directory. If workers are in `workers/`, a project-level `tools.py` won't be found.

2. **Simpler mental model**: Project root = registry root. Workers live alongside `tools.py` and other project files.

3. **Registry search**: `_get_search_paths()` will need updating - it currently searches `workers/` subdirectory by convention. After flattening, it searches the registry root directly.

### Updated Search Paths

After removing workshop, worker search becomes:
```python
def _get_search_paths(self, name: str) -> list[Path]:
    # 1. Explicit paths (./foo.worker, /abs/path.worker)
    # 2. Simple form at root: {root}/{name}.worker
    # 3. Directory form at root: {root}/{name}/worker.worker
    # 4. Generated workers (this session only)
    # 5. Built-in workers
```

The `workers/` subdirectory search is removed.

## Test Strategy

- Test explicit path resolution (`./path/to/worker.worker`)
- Test name resolution (`worker_name` → `workers/worker_name.worker`)
- Test directory-form workers (`workers/name/worker.worker`)
- Test that `toolsets:` configuration still works unchanged
- Test custom tools discovery (worker-local `tools.py`)
- Test error cases (worker not found, invalid path)

## Completed Prerequisites

- **Workers-as-tools**: ✅ `AgentToolset` implemented in `llm_do/agent_toolset.py`
- **ToolContext Protocol**: ✅ in `llm_do/types.py`
- **Depth tracking**: ✅ in `llm_do/runtime.py`

## References

- AgentToolset (workers as tools): `llm_do/agent_toolset.py`
- Current workshop: `llm_do/workshop.py`
- Registry: `llm_do/registry.py`
- Types: `llm_do/types.py`
- Toolset loader: `llm_do/toolset_loader.py`
