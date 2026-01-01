# Ctx Runtime Review

## Context
Review of ctx_runtime core (`llm_do/ctx_runtime/*`) for bugs, inconsistencies, and overengineering.

## Findings
- **Message history:** Top-level runs can pass `message_history` to the model; nested worker calls still start with a clean history (`_should_use_message_history`).
- **Approval wrapping:** Wrapping is centralized in `llm_do/ctx_runtime/approval_wrappers.py` (`wrap_entry_for_approval(...)`) and applied at the `run_entry(...)` boundary; it preserves `Worker` fields and is cycle-safe.
- **Python discovery module re-exec:** CLI discovery uses `load_toolsets_and_workers_from_files()` to avoid importing the same `.py` twice.
- **Per-worker approval config mutates shared instances:** `_approval_config` is stored on existing toolset instances from `ToolsetBuildContext.available_toolsets` (notably Python toolset instances + worker stubs). If multiple workers reference the same Python toolset with different `_approval_config`, the last assignment wins globally.
- **`ctx_runtime/builtins.py` looks superseded:** built-in alias handling lives in `llm_do/toolset_loader.py` (`BUILTIN_TOOLSET_ALIASES`), but `llm_do/ctx_runtime/builtins.py` still exists and is exported; this duplication makes it unclear which is canonical.

## Open Questions
- Should top-level worker runs reuse `message_history` while nested worker calls always start from a clean history? (Current intent appears “yes”.)
- Are cyclic worker references intended to work? If yes, where should cycle detection/error reporting live (resolution vs runtime depth enforcement)?
- Do we want per-worker configuration (especially `_approval_config`) for Python toolsets, or should Python toolset instances be treated as global singletons with uniform config?

## Conclusion
Ctx runtime is close to the intended architecture. Message-history propagation, one-pass module discovery, and the approval wrapping boundary have been clarified, but shared toolset config mutation (`_approval_config`) and duplicated builtins registries remain follow-ups.
