# Simplify: runtime/shared.py

Periodic simplification review of `llm_do/runtime/shared.py`.

## Context Gathering

1. Read the target module in full
2. Identify imports from within the project (`llm_do.*` only, skip stdlib/third-party)
3. Read relevant parts of those internal dependencies for context

Focus analysis on the target module, but use imported code to spot simplifications—duplicate logic, underused abstractions, replaceable inline code. Proposed changes may span multiple files if warranted.

## Simplification Prompt

Analyze for:
1. **Redundant validation** - Checks already handled by dependencies
2. **Over-specified interfaces** - Multiple primitives when one object would do
3. **Unused flexibility** - Options/config never actually used
4. **Redundant parameters** - Values accessible via other parameters
5. **Duplicated derived values** - Same computed value in multiple places

Prioritize: Remove code, reduce concept duplication, make bugs impossible.

## Output

`docs/notes/reviews/simplify-runtime-shared.md`

