# Task 70: Simplify Worker Invocation

## Goal

Simplify the CLI invocation model by eliminating explicit `.worker` file paths as arguments. Use `--dir` and `--tool` flags for explicit, unambiguous invocation.

Directory-form workers (storage format) remain supported — only the invocation syntax changes.

## Current State

The current invocation model has multiple modes:

```bash
# Plain name - search in cwd
llm-do analyzer "message"

# Explicit .worker path - registry = parent directory
llm-do ./path/to/analyzer.worker "message"
```

Problems:
- Ambiguity between message and path arguments
- `InvocationMode` enum adds complexity for invocation (not storage)
- `detect_invocation_mode()` / `resolve_worker()` logic is fragile

## New Design

```bash
# Run main.worker in cwd
llm-do "message"

# Run main.worker in specified directory
llm-do --dir /some/path "message"

# Run specific worker in cwd
llm-do --tool analyzer "message"

# Run specific worker in specified directory
llm-do --dir /some/path --tool analyzer "message"
```

### Rules

1. **`--dir`** (optional): registry root (defaults to `.`)
2. **`--tool`** (optional): tool name, not a path (defaults to `main`)
3. **Positional**: the message/input

**Note:** `--tool` accepts simple names only (e.g., `analyzer`), not paths. Use `--dir` to point to a different registry.

### Worker Storage (unchanged)

Workers can still be stored in either form:

| Form | Path | Capabilities |
|------|------|--------------|
| **Single-file** | `{root}/{name}.worker` | Portable, built-in tools only |
| **Directory** | `{root}/{name}/worker.worker` | Custom `tools.py`, local templates |

Registry searches both paths when loading a worker by name.

### Relocatable Workers

A "relocatable worker" is just a worker project you point to with `--dir`:

```bash
cd /some/project-to-analyze
llm-do --dir ~/code-analyzer "analyze the code in current directory"
```

The worker's filesystem tools operate on CWD (the target directory).

### CWD vs --dir Behavior

**Explicit rule:**

| Flag | Purpose | Affects |
|------|---------|---------|
| `--dir` | Registry root | Where workers, `tools.py`, and templates are loaded from |
| CWD | Working directory | Where filesystem tools operate (unchanged by `--dir`) |

This separation enables relocatable workers:
- Worker code lives in `--dir` (e.g., `~/code-analyzer/`)
- Worker operates on files in CWD (e.g., `/project-to-analyze/`)

The filesystem toolset's `base_path` defaults to `"."` which resolves to CWD at runtime, not to `--dir`.

## Implementation Steps

### 1. Update CLI argument parsing (`cli_async.py`)

- Remove `worker` positional argument
- Add `--dir` flag (defaults to `.`)
- Add `--tool` flag (defaults to `main`)
- Keep `message` as positional argument
- Rename existing `--registry` to `--dir` (or remove if redundant)

### 2. Simplify registry (`registry.py`)

- `_get_search_paths()`: keep both forms (simple and directory)
- `find_custom_tools()`: keep checking `{root}/{name}/tools.py` then `{root}/tools.py`
- `list_workers()`: keep globbing both `*.worker` and `*/worker.worker`
- No changes needed to storage/loading — only invocation changes

### 3. Remove workshop.py complexity

- Remove `InvocationMode` enum from `types.py`
- Remove `detect_invocation_mode()`
- Remove `resolve_worker()` (no longer needed)
- Delete `workshop.py` if empty

### 4. Verify runtime (`runtime.py`)

- Confirm no `InvocationMode` usage (already clean)
- No changes expected

### 5. Update tests

- Remove invocation-mode tests (`TestDetectInvocationMode`, `TestResolveWorker` in `test_workshop.py`)
- Keep directory-form storage tests (storage format is unchanged)
- Update CLI invocation tests for new flag syntax
- Add tests for `--dir` and `--tool` flags

### 6. Update documentation

- `docs/cli.md`: update invocation examples
- `README.md`: update examples
- `docs/concept.md`: keep directory-form storage docs, update invocation examples

### 7. Migration

- [x] `llm-do init` now creates `main.worker` (done)
- Ensure `main.worker` convention is documented
- Update any examples that use explicit `.worker` paths

## Files to Modify

- `llm_do/cli_async.py` - argument parsing
- `llm_do/registry.py` - search path simplification
- `llm_do/workshop.py` - remove or delete
- `llm_do/types.py` - remove `InvocationMode`
- `llm_do/runtime.py` - simplify worker resolution
- `tests/test_cli_async.py` - update tests
- `tests/test_workshop.py` - remove or update
- `docs/concept.md` - update documentation
- `docs/cli.md` - update documentation

## Acceptance Criteria

- [x] `llm-do "message"` runs `main.worker` in cwd
- [x] `llm-do --tool analyzer "message"` runs `analyzer.worker` in cwd
- [x] `llm-do --dir /path "message"` runs `main.worker` in `/path`
- [x] `llm-do --dir /path --tool analyzer "message"` runs `analyzer.worker` in `/path`
- [x] No explicit `.worker` file paths as CLI arguments
- [x] Directory-form storage still works (`analyzer/worker.worker` + `analyzer/tools.py`)
- [x] All tests pass
- [x] Documentation updated
