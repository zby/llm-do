# Simplify: runtime/entry_resolver.py

## Context
Review of manifest entry resolution helpers.

## Findings
- Path handling is duplicated across `_split_function_ref()`, `_is_path_ref()`,
  and `_normalize_python_paths()`. A single helper that parses and resolves
  `path.py:function` references could remove branching.
- `_normalize_python_paths()` builds a set of allowed paths for every entry
  resolution. If entry resolution happens once per run, it could accept a
  pre-resolved set to avoid repeated normalization.
- Relative-path resolution logic mirrors `input_model_refs`. Consider sharing a
  common path-ref helper to reduce duplicate rules.

## Open Questions
- Should we allow module references (non-path) for `entry.function`, or is the
  path-only requirement intentional for safety?
