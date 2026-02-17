---
description: How I process, connect, and maintain knowledge about llm-do
type: moc
---

# methodology

## Principles

- Prose-as-title: every note is a proposition, not a topic label
- Wiki links: connections between notes, ADRs, and tasks as graph edges
- Indexes: attention management hubs that organize notes by area
- Capture fast, process slow — arscontexta/inbox/ for quick thoughts, docs/notes/ for developed ideas

## My Process

### Extract
Read a source (design doc, PR discussion, research paper) and pull out insights relevant to llm-do. Each insight becomes a note with a propositional title and proper frontmatter.

### Connect
After creating or updating a note, find relationships to existing notes, ADRs, and tasks. Add wiki links and update relevant indexes.

### Review
Check note quality: does the description add information beyond the title? Are areas assigned? Is it linked to at least one index?

### Revisit
When the library evolves, update older notes with new context. Flag notes that reference outdated architecture or removed features.

## Boundaries

- Public docs (docs/*.md) stay clean — no frontmatter beyond what the project already uses
- The existing tasks/ workflow is authoritative for task management
- Agent learnings go to docs/notes/agent-learnings/ per AGENTS.md convention

---

Topics:
- [[identity]]
