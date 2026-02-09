# Simplify: project/registry.py

## Context
Review of two-pass registry assembly for Python and `.agent` definitions.

## 2026-02-09 Review
- `build_registry()` still owns multiple responsibilities: loading, conflict checks, model selection, tool/toolset resolution, and input-model resolution. Splitting into staged builders would reduce cognitive load.
- Agent toolsets are materialized for every agent eagerly. If some environments do not need agent-as-tool indirection, lazy materialization can remove work.
- `_merge_registry()` generic merge helper is small but only used locally; inlining may simplify flow and error messaging context.

## Open Questions
- Do we want all agents always callable as toolsets, or only when explicitly referenced?
