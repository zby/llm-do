# Review: Toolsets

Periodic review of toolset implementations for bugs, inconsistencies, and improvements.

## Scope

- `llm_do/toolsets/` - Filesystem, shell toolsets
- `llm_do/toolsets/loader.py` - Toolset loading and class-path resolution
- `llm_do/shell/` - Shell execution helpers
- `llm_do/runtime/builtins.py` - Built-in toolset registry

## Checklist

- [ ] Toolset APIs are consistent
- [ ] Approval logic (`needs_approval()`) is correct
- [ ] Error handling is appropriate
- [ ] Security boundaries are respected
- [ ] No code duplication across toolsets

## Output

Record findings in `docs/notes/reviews/review-toolsets.md`.

## Last Run

2026-01 (reviewed built-in toolsets + loader; main issue: shell whitelist matching is raw-prefix and can overmatch)
