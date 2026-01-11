# Review: Simplification Opportunities

Periodic review of codebase for simplification opportunities - removing unnecessary abstractions, consolidating duplicate patterns, and streamlining APIs.

## Scope

Review `llm_do/runtime/` and related modules for:
- Unnecessary indirection or abstraction layers
- Duplicate or overlapping concepts that could be unified
- Complex code paths that could be simplified
- Deprecated patterns that can be removed
- Backwards compatibility shims that are no longer needed

## Checklist

- [ ] Entry/Invocable: Are there redundant entry point patterns?
- [ ] Registry: Is discovery/linking more complex than needed?
- [ ] Worker: Are there unused attributes or methods?
- [ ] Toolsets: Is toolset resolution straightforward?
- [ ] Runtime: Are scopes (Runtime vs CallFrame) clear and minimal?
- [ ] Backwards compat: Remove any aliases/shims from previous refactors

## Guidelines

When finding simplification opportunities:
1. Create a task in `tasks/backlog/` with clear scope
2. Ensure tests exist before refactoring
3. Remove deprecated code - don't maintain backwards compatibility aliases
4. Update docs to reflect simplified APIs

## Output

Record findings in `docs/notes/reviews/simplify-runtime-*.md` (split by area if needed).

## Last Run

2026-01 (Entry protocol added, InvocableRegistry renamed to EntryRegistry, @entry decorator added)
