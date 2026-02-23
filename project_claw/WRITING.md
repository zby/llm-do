# Writing Guide for project_claw/

Read this before creating or editing notes, ADRs, indexes, or source reviews. For searching and routing, see the Knowledge System section in the root `CLAUDE.md`.

## Before You Write

Every note must be findable by a future agent who doesn't know it exists. Before saving, check:

1. **Title as claim** — Does it work as prose when linked? `since [title](./title.md)` reads naturally?
2. **Description** — Does it add information beyond the title? Would an agent searching for this concept find it?
3. **Index membership** — Is it linked from at least one index?
4. **Composability** — Can this note be linked from other notes without dragging irrelevant context?

If any answer is "no," fix it before saving.

## Where It Goes

Where a note goes depends on what triggered it:

- **Human request or established pipeline** → main KB (`notes/`, `adr/`, tasks, etc. — see routing table in `CLAUDE.md`)
- **Agent's own observation during work** → `notes/agent-learnings/` (notes only — no tasks or ADRs without human request)

Agent-learnings are periodically reviewed and either promoted to the main KB / AGENTS.md, or deleted. The quality checklist above applies to both — but agent-learnings can be briefer since they'll be curated later.

## Templates

Templates live in `project_claw/templates/`. Each provides frontmatter fields to fill in and a body scaffold for that content type. Copy the appropriate template when creating a new document.

| Template | Content type | Use for |
|----------|-------------|---------|
| `note.md` | Design notes | Freeform exploration, insights, analysis |
| `adr.md` | Architecture decisions | Formal decisions with context/consequences |
| `index.md` | Area indexes | Navigation hubs grouping related notes |
| `source-review.md` | External source analysis | Connecting external material to the project |
| `task-active.md` | Active tasks | In-progress work items |
| `task-backlog.md` | Backlog tasks | Ideas not yet ready for work |
| `task-recurring.md` | Recurring tasks | Periodic reviews and audits |

## Frontmatter

Every internal workspace note has YAML frontmatter. Frontmatter makes notes queryable via ripgrep.

| Field | Required | Constraints |
|-------|----------|------------|
| `description` | Yes | Max 200 chars, must add info beyond title |
| `type` | No | Content type matching the template used (note, adr, index, source-review) |
| `areas` | No | Array of index names this note belongs to |
| `status` | No | current, outdated, speculative |

**`description` is the most important field.** It enables progressive disclosure: read the title and description to decide whether to load the full note.

Task files do not use frontmatter — their status is encoded by directory (backlog/active/completed).

## Links

Internal workspace documents connect via standard markdown links. Each link is an edge in the knowledge graph. Use relative paths from the source file's directory.

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

## Indexes

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
rg -l '.' project_claw/notes/*.md | while read f; do
  fname=$(basename "$f")
  rg -q "$fname" --glob '*.md' project_claw/notes/ || echo "Orphan: $f"
done

# Dangling link detection (links to non-existent files)
rg -o '\]\(([^)]+\.md)\)' project_claw/notes/ -r '$1' --no-filename | sort -u | while read target; do
  [ -f "project_claw/notes/$target" ] || echo "Dangling: $target"
done

# Schema validation
rg -L '^description:' project_claw/notes/*.md    # missing descriptions
```

## Common Pitfalls

### Productivity Porn
Building the knowledge system instead of using it for the library. If you're spending more time on methodology than on design notes, recalibrate. The vault serves the library, not the other way around.

### Temporal Staleness
Design notes become outdated as the library evolves. A note about the runtime architecture from two months ago may reference removed features. Update or archive notes that no longer reflect reality.

### Collector's Fallacy
Accumulating design explorations without distilling them into ADRs or actionable decisions. If your notes grow faster than your decisions, stop capturing and start extracting.
