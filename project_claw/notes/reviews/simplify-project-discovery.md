# Simplify: project/discovery.py

## Context
Review of module loading plus tools/toolsets/agents discovery helpers.

## 2026-02-09 Review
- `load_tools_from_files()`, `load_toolsets_from_files()`, and `load_agents_from_files()` duplicate behavior already covered by `load_all_from_files()`.
- Tool and toolset registry parsing each implement parallel dict/list validation logic; common registry parsing scaffolding would reduce mirrored code.
- `_LOADED_MODULES` global cache has no invalidation API; if hot reload is expected, expose explicit cache reset or remove hidden caching.

## Open Questions
- Do we need both one-pass (`load_all_from_files`) and per-kind loaders, or can callers standardize on one entrypoint?
