# SLOC Reduction Task

Your goal is to reduce the source lines of code (SLOC) in the `llm_do` directory.

## Current State
- Run `sloccount llm_do` to see current line count
- Target: See `scripts/ralph-config.sh` for TARGET_SLOC (run `./scripts/ralph-sloc-check.sh` to see current target)
- All tests and quality checks must pass

## Learning Log - READ THIS FIRST

**Before starting, read `ralph-logs/attempts.md`** to see what has been tried before.
- Don't repeat failed attempts unless you have a different approach
- Learn from what worked and what didn't

## Constraints
- All tests must pass: `uv run pytest`
- Lint must pass: `uv run ruff check .`
- Types must pass: `uv run mypy llm_do`
- The code must remain functionally equivalent

## Strategies for SLOC Reduction

1. **Remove dead code**: Look for unused functions, classes, imports
2. **Consolidate duplicates**: Find repeated patterns that can be unified
3. **Simplify abstractions**: Over-engineered code often has unnecessary layers
4. **Remove comments/docstrings that restate the obvious**: Only if they add no value
5. **Flatten inheritance**: Deep hierarchies often hide simpler solutions
6. **Inline small functions**: If a function is only called once and is trivial
7. **Use more expressive Python**: List comprehensions, walrus operator, etc.
8. **Remove defensive code**: If something "can't happen", don't guard against it
9. **Consolidate similar classes**: Look for classes that could be merged
10. **Remove abstractions that are only used once**: If there's only one implementation, you may not need the interface

## Workflow

1. **Read** `ralph-logs/attempts.md` to see previous attempts
2. **Plan** a reduction that hasn't been tried (or try a different approach to a failed one)
3. **Log your plan** - append to `ralph-logs/attempts.md` BEFORE making changes:
   ```
   ## Attempt N - IN PROGRESS
   Target: <file or area>
   Plan: <what you will try>
   ```
4. **Implement** the change
5. **Test** with `./scripts/ralph-sloc-check.sh`
6. **Update the log** with result:
   - SUCCESS: Note lines saved and commit
   - FAILED: Note why it failed (test errors, type errors, etc.) and revert changes

## Important Notes

- Focus on HIGH IMPACT changes - one big simplification is better than many tiny ones
- Read the code carefully before changing it
- Git commit successful changes with a descriptive message
- Do NOT add new features - only simplify existing code
- **Always update the attempts log** - this helps future iterations learn

## Check Your Progress

```bash
./scripts/ralph-sloc-check.sh
```

Keep iterating until the check script returns success (exit code 0)!
