# Instructions for Claude and AI Assistants

## Key References

- `README.md` — setup, CLI usage, examples
- `docs/architecture.md` — internal design, agent delegation, approval system
- `kb/notes/` — working design documents and explorations
- `examples/pitchdeck_eval/` — reference implementation for multi-agent patterns

## Development

- For executing python scripts use `uv run` - the global environment does not have all dependencies
- Test agent features by creating example projects in `examples/` and running with `llm-do`
- Do not preserve backwards compatibility; with no external consumers, always prioritize cleaner design over keeping old behavior alive
- **YAGNI**: Don't implement features that aren't needed yet. If you identify a gap in the spec, create a note in `kb/notes/` instead of implementing it
- Favor clear architecture over hacks; delete dead code when possible
- If backcompat code is ever needed, mark it with `# BACKCOMPAT: <reason> - remove after <condition>` so it can be identified and removed later

### Documentation Examples

When writing examples that use live models:
- Use `anthropic:claude-haiku-4-5` as the primary model (cost-effective)
- Include `openai:gpt-4o-mini` as an alternative
- README examples should always show execution with live models, not placeholders

### Agent Design

- Keep each agent focused on a single unit of work; use `call_agent` for sub-tasks
- Document available tools in `instructions` so models know how to call them

## Architecture & Design Discussions

When working on code architecture, interface design, or system modeling, act as a **full research collaborator** rather than a terse advisor. This means:

- Speak at length about design trade-offs, alternatives considered, and reasoning
- Surface your own concerns, hunches, and open questions proactively
- Engage with the human's ideas critically — push back, extend, or redirect as needed
- Share and probe mental models — how you conceptualize the system, where the boundaries are, what analogies inform your thinking
- Treat the conversation as joint exploration, not Q&A

This collaborative mode applies to: runtime design, API boundaries, data flow, abstraction choices, naming conventions, and similar structural decisions. For routine implementation tasks, the standard concise style remains appropriate.

## Quality Checks

Run relevant checks before submitting changes:
- **Lint**: `uv run ruff check .`
- **Typecheck**: `uv run mypy llm_do`
- **Tests**: `uv run pytest` — all tests must pass. Tests use dummy models, no API calls needed.
- **Inline snapshots**: when changing `snapshot(...)` assertions, run `uv run pytest <target> --inline-snapshot=fix` and review rewritten diffs before final test runs.

**Never claim checks passed unless they were actually run.** If checks cannot be run, explicitly state why.

## Git

- Do not use `git -C <path>` - it complicates approval rules
- Assume you are already in the project directory and run git commands directly
- **Never** `git add -A` — review `git status` and stage specific files
- **Prefer atomic stage+commit** — combine staging and committing in one command (`git add <files> && git commit -m "..."`). Leaving files staged without committing risks another agent's commit sweeping in unrelated changes.
- Check `git diff` before committing
- **Never** use `git reset --hard` or force-push without explicit permission
- Prefer safe alternatives: `git revert`, new commits, temporary branches

---

# Knowledge System

This project uses **[commonplace](commonplace/README.md)** — a reactive, AI-native knowledge system. The project's content lives in `kb/`; the framework (methodology, types, skills, scripts) lives in `commonplace/` (symlinked from sibling repo).

**If it won't exist next session, write it down now.**

## How it loads

- **`CLAUDE.md`** (this file) — always loaded. Routing table, search patterns, guardrails.
- **`kb/WRITING.md`** — read on demand when creating/editing KB content.
- **Skills** (`.claude/skills/`) — descriptions always loaded; skill bodies loaded on invoke.
- **Methodology** (`commonplace/kb/notes/`) — consulted on demand for edge cases skills don't cover.

**Boundary:** Public project documentation (`docs/*.md`) is NOT part of the knowledge system. `kb/` is where the knowledge system operates. `commonplace/` contains the framework and methodology.

## Where Things Go

| Content Type | Destination |
|-------------|-------------|
| llm-do design notes and insights | `kb/notes/` |
| Architecture decisions | `kb/notes/adr/` |
| Project tasks | `kb/tasks/` (read `kb/tasks/README.md` before creating) |
| Code review output | `kb/code-reviews/` |
| External source snapshots | `kb/sources/` |
| Knowledge system methodology | `commonplace/kb/notes/` (don't write here — it's the framework) |

For the `notes/` vs `adr/` boundary: "Is this durable knowledge or a formal decision?"

## When to Write a Note

Write a note when something would be lost between sessions:
- Friction or gotchas worth documenting
- Patterns that should become conventions
- Corrections received that reveal missing guidance
- Design insights or trade-offs discovered during work
- Tool-specific behaviors worth codifying

If it matters and won't exist next session, write it down now.

**Agent-initiated observations** go to `kb/notes/agent-learnings/` — just create a markdown file with a title and some text, no frontmatter needed. A file without frontmatter is a `text` file: the lowest-ceremony base type, meant for quick capture.

**For main KB work** (human-requested notes, ADRs, source reviews), read `kb/WRITING.md` for templates, link conventions, and quality checks.

## Searching the KB

```bash
# Scan descriptions for a concept
rg '^description:.*runtime' kb/notes/

# Find notes by type or area
rg '^type: source-review' kb/notes/
rg 'areas:.*architecture' kb/notes/

# Find backlinks to a specific note
rg '\[.*\]\(.*note-title\.md\)' --glob '*.md' kb/

# Search methodology (when skills don't cover the edge case)
rg 'pattern' commonplace/kb/notes/
```

### qmd (semantic search)

Always use `--index llm-do` to scope searches to this project:
```bash
qmd --index llm-do query "concept"
qmd --index llm-do search "keyword"
qmd --index llm-do update        # re-index after changes
```

## Guardrails

- Never present inferences as facts — "I notice a pattern" not "this is true"
- Never fabricate sources or citations
- The vault serves the library, not the other way around

---

Stay small, stay testable, trust the LLM.

For the arscontexta processing pipeline, skills, operational space, and session rhythm, see `arscontexta/CLAUDE.md`.
