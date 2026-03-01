# Simplify: project/entry_resolver.py

## Context
Review of manifest entry target resolution.

## 2026-02-09 Review
- `_resolve_function_entry()` recomputes normalized allowed paths each call; passing pre-normalized paths from manifest resolution would reduce repeated work.
- Error-shaping and path-syntax validation are split across `_split_function_ref`, `is_path_ref`, and direct checks; consolidating parse+resolve into one helper would simplify control flow.
- Function-loading logic (`load_module`, `getattr`, callable/async checks) is cohesive and could be extracted as reusable `resolve_async_callable_ref` for other path-ref use cases.

## Open Questions
- Should `entry.function` continue to allow only path refs, or also support importable module refs?
