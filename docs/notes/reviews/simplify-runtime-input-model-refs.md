# Simplify: runtime/input_model_refs.py

## Context
Review of input model reference resolution for agent files.

## Findings
- Path-vs-module detection logic duplicates `entry_resolver`. Consider sharing
  a common helper for path refs to reduce parallel parsing rules.
- `_split_input_model_ref()` accepts both `module.Class` and `path.py:Class`.
  If one syntax is preferred, narrowing to a single form would simplify
  parsing and error messages.
- `_load_model_module()` handles relative paths with `base_path`, which mirrors
  logic elsewhere. Centralizing base-path resolution would reduce drift.

## Open Questions
- Is supporting both dot and colon syntax required, or can we standardize on
  `path.py:Class`?
