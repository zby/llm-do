# Simplify: runtime/tooling.py

## Context
Review of runtime-owned tool/toolset type aliases and predicate helpers.

## 2026-02-09 Review
- `ToolDef`/`ToolsetDef` aliases and `is_tool_def`/`is_toolset_def` predicates are a thin compatibility surface that should remain centralized in this module.
- Predicates are intentionally broad (`callable(...)`), which keeps flexibility but weakens validation precision. Consider tightening to explicit accepted runtime shapes if dynamic flexibility is no longer needed.
- `tool_def_name()` is the only non-trivial helper here; if aliases move closer to project resolution code, keep only this helper in runtime.

## 2026-02-11 Cleanup
- `llm_do/toolsets/loader.py` was removed.
- `llm_do/runtime/tooling.py` is now the single source of truth for tool/toolset aliases and predicates.
