# Simplify: project/tool_resolution.py

## Context
Review of tool/toolset reference resolution from string names to runtime defs.

## 2026-02-09 Review
- `_wrap_toolset_func_validation()` mirrors dynamic toolset-return validation used in runtime call wrapping; a shared validation helper would remove duplicate semantics.
- `resolve_tool_defs()` and `resolve_toolset_defs()` have parallel lookup/error skeletons that can be factored into one typed resolver template.
- `_attach_registry_name()` relies on best-effort attribute mutation; if registry names become first-class, consider explicit wrapper objects over setattr side effects.

## Open Questions
- Is `_llm_do_registry_name` intended as stable runtime contract or internal trace metadata?
