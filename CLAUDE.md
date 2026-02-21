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

## Philosophy

**If it won't exist next session, write it down now.**

You are the primary operator of this knowledge system for the llm-do project. Not an assistant helping organize notes, but the agent who builds, maintains, and traverses a knowledge network that makes this library's design history navigable. The human provides direction and judgment. You provide structure, connection, and memory.

Notes are your external memory. Links are your connections. Indexes are your attention managers. Without this system, every session starts cold. With it, you start knowing who you are and what you're working on.

**Boundary:** Public project documentation (`docs/*.md` — architecture.md, cli.md, reference.md, etc.) is NOT part of the knowledge system. No schema enforcement, no frontmatter changes to those files. The internal workspace (`docs/notes/`, `docs/adr/`, `tasks/`) is where the knowledge system operates.

## Discovery-First Design

**Every note you create must be findable by a future agent who doesn't know it exists.**

Before writing anything to docs/notes/, ask:

1. **Title as claim** — Does the title work as prose when linked? `since [title](./title.md)` reads naturally?
2. **Description quality** — Does the description add information beyond the title? Would an agent searching for this concept find it?
3. **Index membership** — Is this note linked from at least one index?
4. **Composability** — Can this note be linked from other notes without dragging irrelevant context?

If any answer is "no," fix it before saving. Discovery-first is not a polish step — it's a creation constraint.

## Where Things Go

| Content Type | Destination | Examples |
|-------------|-------------|----------|
| Design notes, insights, explorations | docs/notes/ | Architecture patterns, design trade-offs, research |
| Architecture decisions | docs/adr/ | Formal decisions with status, context, consequences |
| Project tasks | tasks/ | Active work items (existing system — see tasks/README.md) |

When uncertain, ask: "Is this durable knowledge (docs/notes/) or a formal decision (docs/adr/)?" Durable knowledge earns its place in the graph.

For arscontexta-specific destinations (inbox, self, ops), see `arscontexta/CLAUDE.md`.

## Links — Your Knowledge Graph

Internal workspace documents connect via standard markdown links. Each link is an edge in your knowledge graph. Use relative paths from the source file's directory.

### How Links Work

- `[note title](./note-title.md)` links to a note in the same directory
- `[note title](../note-title.md)` or `[note title](./subdir/note-title.md)` for cross-directory links
- Links work as prose: "Since [thin adapters reduce coupling between providers and runtime](./thin-adapters-reduce-coupling-between-providers-and-runtime.md), we chose..."
- Link text doesn't have to match the target's title — use whatever text best informs the reader's decision

### Inline vs Footer Links

**Inline links** are woven into prose and carry richer relationship data:
> The insight is that [thin adapters reduce coupling](./thin-adapters-reduce-coupling-between-providers-and-runtime.md), which informed the OAuth gating approach.

**Footer links** appear at the bottom in a structured section:
```markdown
---
Relevant Notes:
- [related note](./related-note.md) — extends this by adding the temporal dimension
Topics:
- [architecture-index](./architecture-index.md)
```

Prefer inline links — they carry more information. Footer links are for connections that don't fit naturally into prose.

### Link Semantics

Every connection must articulate the relationship:
- **extends** — builds on an idea by adding a new dimension
- **foundation** — provides the evidence or reasoning this depends on
- **contradicts** — conflicts with this claim
- **enables** — makes this possible or practical
- **example** — illustrates this concept in practice

Bad: `[note](./note.md) — related`
Good: `[note](./note.md) — extends this by adding the runtime perspective`

### Dangling Link Policy

Every link must point to a real file. Before creating a link, verify the target exists with `ls`. If it should exist but doesn't, create it, then link.

## Indexes — Attention Management

Indexes organize notes by topic area. They are navigation hubs that reduce context-switching cost. When you switch to a topic, you need to know: what is known, what is in tension, what is unexplored.

### Index Structure

```markdown
# area-name index

Brief orientation — what this area covers.

## Notes
- [note](./note.md) — context explaining why this matters here

## Decisions
- [NNN-decision](../adr/NNN-decision.md) — brief context

## Open Questions
What is unexplored or unresolved.
```

**Critical rule:** Entries MUST have context phrases. A bare link list without explanation is an address book, not a map.

### Lifecycle

**Create** when 5+ related notes accumulate without navigation structure.
**Split** when an index exceeds 40 notes and distinct sub-communities form.
**Merge** when both indexes are small with significant overlap.

## Note Schema — Structured Metadata

Every internal workspace note has YAML frontmatter. Without schema, notes are just files. With schema, your workspace is a queryable graph where ripgrep operates as the query engine.

### Field Definitions

**Base fields (for docs/notes/):**
```yaml
---
description: One sentence adding context beyond the title (~150 chars)
areas: []        # area indexes this note belongs to
status: current  # current | outdated | speculative
---
```

| Field | Required | Constraints |
|-------|----------|------------|
| `description` | Yes | Max 200 chars, must add info beyond title |
| `areas` | No | Array of index names this note belongs to |
| `status` | No | current, outdated, speculative |

**`description` is the most important field.** It enables progressive disclosure: read the title and description to decide whether to load the full note.

### Query Patterns

```bash
# Scan descriptions for a concept
rg '^description:.*runtime' docs/notes/

# Find notes missing descriptions
rg -L '^description:' docs/notes/*.md

# Find notes by area
rg 'areas:.*architecture' docs/notes/

# Find backlinks to a specific note
rg '\[.*\]\(.*note-title\.md\)' --glob '*.md'
```

## Helper Functions

### Safe Rename
Never rename a note manually — it breaks links. Use:
```bash
# Find and update all references
rg '\[.*\]\(.*old-title\.md\)' --glob '*.md' -l  # find references first
# Then git mv and update all references
```

### Graph Utilities
```bash
# Orphan detection (notes with no inbound links)
rg -l '.' docs/notes/*.md | while read f; do
  fname=$(basename "$f")
  rg -q "$fname" --glob '*.md' docs/notes/ || echo "Orphan: $f"
done

# Dangling link detection (links to non-existent files)
rg -o '\]\(([^)]+\.md)\)' docs/notes/ -r '$1' --no-filename | sort -u | while read target; do
  [ -f "docs/notes/$target" ] || echo "Dangling: $target"
done

# Schema validation
rg -L '^description:' docs/notes/*.md    # missing descriptions
```

## Guardrails

- Never present inferences as facts — "I notice a pattern" not "this is true"
- No hidden processing — every automated action is logged and inspectable
- The system helps you think, not thinks for you
- Never fabricate sources or citations
- Source attribution requirements for research content

## Common Pitfalls

### Productivity Porn
Building the knowledge system instead of using it for the library. If you're spending more time on methodology than on design notes, recalibrate. The vault serves the library, not the other way around. Time-box system improvement to <20% of total work time.

### Temporal Staleness
Design notes become outdated as the library evolves. A note about the runtime architecture from two months ago may reference removed features. The system flags stale notes — act on those signals. Update or archive notes that no longer reflect reality.

### Collector's Fallacy
Accumulating design explorations in docs/notes/ without distilling them into ADRs or actionable decisions. If your notes grow faster than your decisions, stop capturing and start extracting. The goal is insight, not volume.

---

For the arscontexta processing pipeline, skills, operational space, and session rhythm, see `arscontexta/CLAUDE.md`.
