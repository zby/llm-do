# Simplify runtime/deps.py

## Status
ready for implementation

## Prerequisites
- [x] none

## Goal
Run the simplification prompt on `llm_do/runtime/deps.py` and its local imports, producing a review report with proposed simplifications.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/deps.py` (primary target)
  - Local imports from this repo (contracts.py, shared.py, etc.)
- Output:
  - `docs/notes/reviews/simplify-runtime-deps.md`

## Simplification Prompt

Analyze this codebase for simplification opportunities. Look for patterns like:

1. **Redundant validation** - Checks that are already handled by a dependency or framework. If a library you depend on already validates something, your duplicate check adds complexity without value.

2. **Unused flexibility** - Data structures that support configuration or options that are never actually used. Examples:
   - Dict values that are always empty `{}`
   - Optional parameters that always receive the same value
   - Generic types that are always instantiated the same way
   Consider whether the flexibility will ever be needed, or if it should be pushed to a different layer.

3. **Redundant parameters** - Function parameters that pass values already accessible via other parameters. If you pass `obj` and also `obj.x`, the second parameter is redundant and creates maintenance risk (they could get out of sync).

4. **Duplicated derived values** - The same computed/formatted value appearing in multiple places. Examples:
   - Format strings like `f"[{worker}:{depth}]"` repeated across methods
   - Computed properties recalculated instead of stored
   These should be centralized into a single property or method. This prevents inconsistency bugs.

5. **Over-specified interfaces** - Passing multiple primitive values when a single object would do, especially when those values are always used together or derived from the same source.

For each opportunity found:
- Explain what pattern it matches
- Show the current code
- Propose the simplified version
- Note any judgment calls required (e.g., "this removes flexibility that might be needed")
- Flag if the simplification would have prevented any existing inconsistencies

Prioritize changes that:
- Remove code rather than add it
- Reduce the number of places where a concept is defined
- Make it impossible (not just unlikely) for certain bugs to occur

## Tasks
- [ ] Read deps.py and identify its local imports
- [ ] Analyze with the simplification prompt above
- [ ] Write review report to `docs/notes/reviews/simplify-runtime-deps.md`

## Current State
Not started.

## Notes
- Deps module handles dependency injection for toolsets; simplifications improve the mental model of how dependencies flow through the system
