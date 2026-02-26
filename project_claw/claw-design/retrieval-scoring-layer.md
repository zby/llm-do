---
description: Metadata-aware reranking over semantic search — type-dependent recency decay, per-note overrides, SQLite index rebuilt from frontmatter
type: note
traits: []
areas: [claw-design]
status: speculative
---

# Retrieval needs a metadata-aware scoring layer

Semantic search (qmd) finds conceptually related content but treats all results equally. The [patterns proven in practice](./what-works.md) — frontmatter queries via rg, semantic search via qmd — handle discovery well, but some queries need metadata-aware ranking: "recent practitioner reports about agent memory" requires understanding that practitioner reports decay in relevance faster than design principles.

## The gap

A query like "what's new in agent frameworks" should weight a blog post from yesterday higher than one from six months ago. But a query like "what are the design principles for tool interfaces" should not penalize older notes — those are often more refined.

This requires scoring logic that understands frontmatter metadata (type, captured date, status) and applies it differently per content type.

## Proposed architecture

A scoring layer that wraps qmd results:

```
query → qmd (semantic relevance) → scoring layer (metadata-aware reranking) → results
```

Since [files stay the source of truth](./files-not-database.md), the scoring layer reads from a derived index rather than replacing qmd.

### Scoring policies by type

Different content types have different relevance decay — the same intuition behind [cludebot's explicit staleness decay](./what-cludebot-teaches-us.md) (episodic 7%/day, semantic 2%/day) and the [three-space model's metabolic rates](./three-space-agent-memory-maps-to-tulving-taxonomy.md) (knowledge accumulates, operational artifacts churn):

- `blog-post`, `github-issue` → strong recency signal (these go stale)
- `scientific-paper`, design notes → no recency decay (timeless)
- `practitioner-report` → moderate recency decay (practices evolve)

### Per-type defaults with per-note overrides

- Types have default decay policies defined in code — this depends on [document types being verifiable](./document-types-should-be-verifiable.md), since the scoring function can only apply per-type policies if the type field is trustworthy
- Individual notes can override via frontmatter (e.g. `decay: none` on a blog post that's actually timeless)
- Scoring function: `score(semantic_score, metadata, query_context) -> float`

### SQLite index over frontmatter

A lightweight SQLite database rebuilt from frontmatter on demand — a build artifact, not source of truth:

```
uv run project_claw/scripts/rebuild_index.py  # scans .md frontmatter → SQLite
```

This extends the pattern qmd already uses — an index over files, not a replacement for them. If the index gets corrupted, rebuild it.

---

Relevant Notes:
- [files beat a database](./files-not-database.md) — grounds this proposal: the scoring layer is a derived index over files, not a replacement for them
- [what works](./what-works.md) — the qmd + frontmatter patterns this proposal extends with metadata-aware reranking
- [what cludebot teaches us](./what-cludebot-teaches-us.md) — the staleness decay idea (per-type decay rates) that this note concretizes into an implementable architecture
- [three-space agent memory maps to Tulving's taxonomy](./three-space-agent-memory-maps-to-tulving-taxonomy.md) — the metabolic rate framework that per-type decay operationalizes
- [document types should be verifiable](./document-types-should-be-verifiable.md) — prerequisite: per-type scoring policies require types that agents and scripts can trust

Topics:
- [claw-design](./claw-design.md)
