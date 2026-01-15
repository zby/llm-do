# Simplify: ui/app.py

Periodic simplification review of `llm_do/ui/app.py`.

## Context Gathering

1. Read the target module in full
2. Identify imports from within the project (`llm_do.*` only, skip stdlib/third-party)
3. Read relevant parts of those internal dependencies for context

Focus analysis on the target module, but use imported code to spot simplifications—duplicate logic, underused abstractions, replaceable inline code. Proposed changes may span multiple files if warranted.

## Simplification Prompt

Analyze for:
1. **Redundant validation** - Checks already handled by dependencies
2. **Unused flexibility** - Options/config never actually used
3. **Redundant parameters** - Values accessible via other parameters
4. **Duplicated derived values** - Same computed value in multiple places
5. **Over-specified interfaces** - Multiple primitives when one object would do

Prioritize: Remove code, reduce concept duplication, make bugs impossible.

## Output

`docs/notes/reviews/simplify-ui-app.md`

## Last Run

(not yet run)
