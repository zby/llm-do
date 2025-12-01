# Registry Redesign: PYTHONPATH-like Search Path

**Date:** 2025-11-26
**Status:** Implemented (Phase 1 - Generated Workers)

## Problem

The current registry uses a single-root model:
- One `--registry` path (defaults to cwd)
- Searches: `{root}/workers/` → `{root}/workers/{name}/` → `{root}/workers/generated/` → built-ins

This doesn't match programmer intuition from PYTHONPATH, which is a colon-separated list of multiple paths searched in order.

## Design Decision

Separate **finding workers** (read) from **generating workers** (write).

### Phase 1: Generated Workers (IMPLEMENTED)

Generated workers now go to `/tmp/llm-do/generated/` as **self-contained directories** with session-scoped visibility.

**Directory structure:**
```
/tmp/llm-do/generated/
└── my_worker/
    ├── worker.worker      # definition (required)
    ├── my_worker.txt    # prompt file (optional)
    └── tools.py         # custom tools (optional, future)
```

**Key behaviors:**
1. Generated workers are saved to `/tmp/llm-do/generated/{name}/worker.worker`
2. Only workers generated in the **current session** are findable via `load_definition()`
3. The registry tracks generated worker names in `_generated_workers: Set[str]`
4. Conflict detection: error if worker name exists anywhere (project, built-in, or generated dir)
5. Never overwrite - strict error on conflict
6. Prompts are resolved from the worker's own directory (self-contained)

**Implementation:**
- `GENERATED_DIR = Path("/tmp/llm-do/generated")` constant in `registry.py`
- `WorkerRegistry` accepts optional `generated_dir` parameter (for testing)
- `registry.register_generated(name)` to make a worker findable
- `registry.worker_exists(name)` checks all locations including generated dir
- `create_worker()` raises `FileExistsError` on conflict

### Phase 2: LLM_DO_PATH (FUTURE)

A colon-separated search path, like PYTHONPATH:

```bash
# Environment variable
export LLM_DO_PATH="./workers:~/.llm-do/workers:/usr/share/llm-do/workers"

# Or CLI override (replaces env var)
llm-do worker --registry "./workers:~/.llm-do"
```

**Semantics:**
- First match wins (leftmost path has highest priority)
- Project-local workers override user/system defaults
- Built-ins are always searched last (implicit, not in path)
- Empty/unset defaults to `.` (current directory)

### Keeping Workers: Standard Unix Tools

To persist a generated worker, use `cp -r`:

```bash
# Inspect what was generated
ls /tmp/llm-do/generated/
cat /tmp/llm-do/generated/my_worker/worker.worker

# Keep a worker (always use -r since they're directories)
cp -r /tmp/llm-do/generated/my_worker/ ./workers/
```

**Rationale:**
- Unix philosophy: compose with standard tools
- No special "promote" or "save" commands needed
- Shell tab-completion works
- Users already know `cp -r`
- Always directories = one consistent command

## Summary

| Concern | Mechanism | Status |
|---------|-----------|--------|
| **Find workers** | Project → Built-in (future: `LLM_DO_PATH`) | Partial |
| **Generate workers** | `/tmp/llm-do/generated/` | ✅ Done |
| **Session isolation** | `registry._generated_workers` set | ✅ Done |
| **Conflict detection** | `registry.worker_exists()` | ✅ Done |
| **Keep workers** | `cp` / `cp -r` to your project | ✅ Done |

## Open Questions (for Phase 2)

1. **Multi-user systems:** Use `/tmp/llm-do/generated/` or `/tmp/llm-do-$USER/generated/`?
   - Current: simpler path since multi-user is rare for this tool

2. **Default `LLM_DO_PATH`:** Should it default to `.` or `.:~/.llm-do`?
   - Leaning toward `.` only (like PYTHONPATH defaults to empty/cwd)
