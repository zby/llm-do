# Instructions for Claude and AI Assistants

Read and follow all guidance in `AGENTS.md`.

## Documentation Examples

When writing examples that use live models:
- Use `anthropic:claude-haiku-4-5` as the primary model (cost-effective)
- Include `openai:gpt-4o-mini` as an alternative
- README examples should always show execution with live models, not placeholders

## Git Usage

- Do not use `git -C <path>` - it complicates approval rules
- Assume you are already in the project directory and run git commands directly

---

# Knowledge System

**If it won't exist next session, write it down now.**

**Boundary:** Public project documentation (`docs/*.md`) is NOT part of the knowledge system. The internal workspace (`project_claw/`) is where the knowledge system operates.

## Where Things Go

| Content Type | Destination |
|-------------|-------------|
| Design notes, insights, explorations | `project_claw/notes/` |
| Architecture decisions | `project_claw/adr/` |
| Project tasks | `project_claw/tasks/` |
| KB design & methodology | `project_claw/kb-design/` |
| External source snapshots | `project_claw/sources/` |

When uncertain: "Is this durable knowledge (notes/) or a formal decision (adr/)?"

## When to Write a Note

Write a note when something would be lost between sessions:
- Friction or gotchas worth documenting
- Patterns that should become conventions
- Corrections received that reveal missing guidance
- Design insights or trade-offs discovered during work
- Tool-specific behaviors worth codifying

If it matters and won't exist next session, write it down now.

**Agent-initiated observations** go to `project_claw/notes/agent-learnings/` — jot quickly with a title and description, don't interrupt the current task. These are reviewed and promoted later.

**For main KB work** (human-requested notes, ADRs, source reviews), read `project_claw/WRITING.md` for templates, link conventions, and quality checks.

## Searching the KB

```bash
# Scan descriptions for a concept
rg '^description:.*runtime' project_claw/notes/

# Find notes by type or area
rg '^type: source-review' project_claw/notes/
rg 'areas:.*architecture' project_claw/notes/

# Find backlinks to a specific note
rg '\[.*\]\(.*note-title\.md\)' --glob '*.md'
```

## Guardrails

- Never present inferences as facts — "I notice a pattern" not "this is true"
- Never fabricate sources or citations
- The vault serves the library, not the other way around

---

For the arscontexta processing pipeline, skills, operational space, and session rhythm, see `arscontexta/CLAUDE.md`.
