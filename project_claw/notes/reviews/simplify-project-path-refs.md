# Simplify: project/path_refs.py

## Context
Review of shared path-ref parsing helpers.

## 2026-02-09 Review
- `is_path_ref()` is heuristic and permissive by design; call sites may still need stronger checks. If path-only contexts grow, introduce stricter parsing mode.
- `resolve_path_ref()` combines relative resolution, fallback policy, and error message shaping; splitting policy from resolution would simplify testing.

## Open Questions
- Should `allow_cwd_fallback=True` remain available, or should all relative refs require explicit `base_path`?
