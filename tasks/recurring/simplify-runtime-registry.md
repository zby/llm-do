# Simplify: runtime/registry.py

Periodic simplification review of `llm_do/runtime/registry.py`.

## Simplification Prompt

Analyze for:
1. **Redundant validation** - Checks already handled by dependencies
2. **Unused flexibility** - Options/config never actually used
3. **Redundant parameters** - Values accessible via other parameters
4. **Duplicated derived values** - Same computed value in multiple places
5. **Over-specified interfaces** - Multiple primitives when one object would do

Prioritize: Remove code, reduce concept duplication, make bugs impossible.

## Output

`docs/notes/reviews/simplify-runtime-registry.md`

## Last Run

2026-01 (redundant maps/assignments, extra conflict check)
