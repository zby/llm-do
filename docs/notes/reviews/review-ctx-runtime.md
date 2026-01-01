# Ctx Runtime Review

## Context
Review of ctx_runtime core (`llm_do/ctx_runtime/*`) for bugs, inconsistencies, and overengineering.

## Findings
- **Message history is wired but not actually used in top-level runs:** `WorkerInvocable.call()` always runs the agent in a spawned child ctx created via `CallFrame.fork()` which sets `messages=[]`; the `agent.run(..., message_history=...)` plumbing reads from that empty list, so chat mode never passes prior messages to the model.
- **Approval wrapping copies `WorkerInvocable` incompletely:** `_wrap_toolsets_with_approval()` and `cli.run()` rebuild `WorkerInvocable` by hand, dropping fields like `model_settings` (and any future fields), which can silently change behavior for Python-defined workers.
- **Approval wrapping can infinite-recurse on cyclic worker graphs:** worker A can reference worker B and vice-versa (allowed by `build_entry`/`build_toolsets`), but `_wrap_toolsets_with_approval()` recursively descends into `WorkerInvocable.toolsets` without cycle detection.
- **Python discovery re-executes modules:** `cli.build_entry()` calls both `load_toolsets_from_files()` and `load_workers_from_files()`; each calls `load_module()` and executes the same `.py` file, so modules with import-time side effects/state can produce toolsets/workers that are out of sync (and it's slower than necessary).
- **Per-worker approval config mutates shared instances:** `_approval_config` is stored on existing toolset instances from `ToolsetBuildContext.available_toolsets` (notably Python toolset instances + worker stubs). If multiple workers reference the same Python toolset with different `_approval_config`, the last assignment wins globally.
- **`ctx_runtime/builtins.py` looks superseded:** built-in alias handling lives in `llm_do/toolset_loader.py` (`BUILTIN_TOOLSET_ALIASES`), but `llm_do/ctx_runtime/builtins.py` still exists and is exported; this duplication makes it unclear which is canonical.

## Open Questions
- Should top-level worker runs reuse `message_history` while nested worker calls always start from a clean history? (Current intent appears “yes”, but implementation is “no”.)
- Are cyclic worker references intended to work? If yes, should approval wrapping be cycle-safe; if no, where should cycle detection/error reporting live?
- Do we want per-worker configuration (especially `_approval_config`) for Python toolsets, or should Python toolset instances be treated as global singletons with uniform config?

## Conclusion
Ctx runtime is close to the intended architecture, but there are a couple of correctness issues (chat message history and double module execution) and some sharp edges (cycle handling, shared config mutation, duplicated builtins registry). Recommended follow-ups: fix message-history propagation, add module caching/one-pass discovery, make approval wrapping preserve `WorkerInvocable` fields and handle cycles, and clarify per-worker toolset config semantics.
