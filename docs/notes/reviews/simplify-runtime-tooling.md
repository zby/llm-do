# Simplify: runtime/tooling.py

## Context
Review of runtime-owned tool/toolset type aliases and predicate helpers.

## 2026-02-09 Review
- `ToolDef`/`ToolsetDef` aliases and `is_tool_def`/`is_toolset_def` predicates are thin compatibility surface and overlap with `llm_do/toolsets/loader.py` re-exports.
- Predicates are intentionally broad (`callable(...)`), which keeps flexibility but weakens validation precision. Consider tightening to explicit accepted runtime shapes if dynamic flexibility is no longer needed.
- `tool_def_name()` is the only non-trivial helper here; if aliases move closer to project resolution code, keep only this helper in runtime.

## Open Questions
- Should `llm_do/toolsets/loader.py` remain as compatibility re-export, or can runtime tooling become the single source of truth?
