# Simplify: runtime/discovery.py

## Context
Review of module loading and discovery helpers.

## Findings
- `load_toolsets_from_files()` and `load_agents_from_files()` duplicate logic
  that already exists in `load_all_from_files()`. Prefer a single entry point
  and have the others delegate or remove them.
- `_discover_from_module()` is only used for agents. If toolset discovery
  stays custom, consider inlining or generalizing it so discovery logic lives
  in one place.
- Module caching (`_LOADED_MODULES`) prevents reloading changed files. If
  hot-reload is not required, keep it; otherwise consider removing the cache
  or adding an explicit reload path to reduce hidden state.

## Open Questions
- Do we rely on module caching across runs, or can we simplify by loading
  modules fresh per invocation?
