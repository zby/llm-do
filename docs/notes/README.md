# Notes

Working documents for exploration, design thinking, and capturing insights.

## Purpose

1. **Exploration** - Research alternatives, analyze tradeoffs, investigate bugs
2. **Offloading** - Complex thinking that doesn't fit in a commit message or code comment
3. **Future reference** - Insights that might be useful later, even if not acted on now

## Usage

- **Creating**: Add to `docs/notes/` when exploring something non-trivial
- **Archiving**: Move to `archive/` when resolved, implemented, or no longer relevant (archived notes are kept as-is)
- **Referencing**: Link from AGENTS.md or tasks when the note informs decisions

## Subdirectories

- `archive/` — resolved or superseded notes (immutable after archiving)
- `agent-learnings/` — staging area for agent-discovered insights (see its README)

## Note Template

```markdown
# Topic Name

## Context
Why this exploration matters. What prompted it.

## Findings
What was learned, discovered, or designed.

## Open Questions
- Unresolved decisions
- Things that need more investigation
- Tradeoffs not yet decided

## Conclusion
(Add when resolved) What was decided and why.
```

## Guidelines

- Notes are for thinking, tasks are for doing
- Include "Open Questions" to mark unresolved points
- Don't let notes become stale — archive or update them
- Permanent decisions belong in AGENTS.md or code, not notes
