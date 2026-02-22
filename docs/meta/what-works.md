---
description: Patterns proven valuable in practice — prose-as-title, template nudges, frontmatter queries, semantic search via qmd, discovery-first, public/internal boundary
type: review
areas: [kb-design]
status: current
---

# What works

Patterns that have proven valuable in practice.

## Prose-as-title convention

Note titles that work as claims when linked make the graph self-documenting. "Since [[thin adapters reduce coupling between providers and runtime]]" reads as prose and tells you what the note argues without opening it. Titles-as-labels ("adapter notes", "runtime thoughts") destroy this property.

## Template fields as behavioral nudges

The `areas: []` field in note templates guides agents to update indexes without explicit rules. The agent fills in the template, hits the empty array, and naturally asks "which index does this belong to?" The CLAUDE.md rule reinforces this, but the template is what makes it automatic. See [the observation](observations/template-areas-field-nudges-index-updates.md) that triggered this directory.

## Discovery-first as creation constraint

Checking findability *before* saving prevents orphan accumulation. Four questions: Does the title work as a claim? Does the description add information beyond the title? Is this linked from at least one index? Can this be linked without dragging irrelevant context? If any answer is no, fix it before saving.

## Frontmatter as queryable structure

YAML frontmatter turns a directory of markdown files into a queryable collection. `rg '^areas:.*architecture' docs/notes/` finds all architecture notes. `rg '^description:.*runtime' docs/notes/` searches summaries without opening files. In practice, `areas` and `description` are the fields that get queried — `description` especially, because it lets you decide whether to read the full note without opening it.

## Semantic search via qmd

`rg` handles structured queries (frontmatter fields, known keywords), but discovering *conceptually related* notes requires semantic search. [qmd](https://github.com/qmdnotes/qmd) runs locally on GPU with embeddings + reranking — no API calls, no latency.

The knowledge base is indexed as collections (`notes`, `adr`, `meta`, `docs`). Three search modes complement each other:

- `qmd search "query"` — BM25 keyword search, fast, good for known terms
- `qmd vsearch "query"` — vector similarity, finds conceptual neighbors even with different vocabulary
- `qmd query "query"` — hybrid: query expansion + keyword + vector + reranking (recommended default)

In practice, `qmd query` with `--files` flag is the workhorse for `/connect` discovery — it finds candidates that `rg` misses because they use different terminology for the same concept. The two tools are complementary: `rg` for structured/exact queries, `qmd` for semantic/fuzzy discovery.

Keeping the index current: `qmd update && qmd embed` re-scans and re-embeds changed files. Both are idempotent and fast.

## Public/internal boundary

Keeping knowledge system artifacts out of public docs (`docs/*.md`) prevents coupling. Public documentation has its own audience and conventions. Internal notes can evolve freely without worrying about external readers.

Topics:
- [kb-design](./kb-design.md)
