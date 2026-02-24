---
description: Auto-generated directory — run scripts/generate_notes_index.py /home/zby/llm/llm-do/project_claw/claw-design to rebuild
type: index
---

# Claw Design Directory

- [ADR-001: Generate Topic links from frontmatter](./adr/001-generate-topic-links-from-frontmatter.md)
- [Arscontexta methodology review](./arscontexta-review.md) *(note)* — Curated extraction of transferable ideas from arscontexta's 250-note methodology collection, filtered for a programmer's perspective — what's genuinely actionable vs philosophical vs system-specific
- [Backlinks — use cases and design space](./backlinks.md) *(note)* — Analysis of where backlinks (inbound link visibility) would concretely help agents working in the KB — use cases, trade-offs, and design options
- [Claw design](./claw-design.md) *(index)* — Index of notes about designing and building the knowledge base itself — what works, what doesn't, how to test it
- [Claw learning is broader than retrieval](./claw-learning-is-broader-than-retrieval.md) *(note)* — A Claw's learning loop must improve action capacity (classification, planning, communication), not just retrieval — question-answering is one mode among many
- [CLAUDE.md is a router, not a manual](./context-loading-strategy.md) *(note)* — CLAUDE.md should be a slim router to task-specific docs, not a comprehensive manual — because it's loaded every session
- [Convert still requires semantic description](./convert-still-requires-semantic-description.md)
- [Document classification](./document-classification.md) *(spec)* — Base types assert verifiable structure (text, note, spec, review, index, adr); traits assert checkable properties; status tracks commitment (seedling vs current) independently of structure
- [Document types should be verifiable](./document-types-should-be-verifiable.md) *(note)* — Document types should assert verifiable structural properties, not subject matter — with a base type + traits model inspired by gradual and structural typing
- [Files beat a database for agent knowledge bases](./files-not-database.md) *(note)* — Files with git beat a database for agent-facing knowledge bases — universal interface, free versioning, no infrastructure to maintain
- [The KB needs a learning loop](./kb-learning-loop-is-an-open-problem.md) *(note)* — The KB's value is question-answering capacity, but designing a learning loop requires more usage history than we currently have
- [Link contracts framework — source material](./link-contracts-framework.md) *(note)* — Reference framework for systematic, testable linking — link contracts, intent taxonomy, automated checks, agent implications
- [Links](./links.md) *(index)* — Index of notes about linking — how links work as decision points, navigation modes, link contracts, and automated link management
- [Needs testing](./needs-testing.md) *(review)* — Promising ideas without enough evidence — extract/connect/review cycle, input classification before processing
- [Agents navigate by deciding what to read next](./observations/agents-navigate-by-deciding-what-to-read-next.md) *(note)* — An agent doing a task navigates by deciding what to read — links, index entries, search tools, and skill descriptions are all pointers with varying amounts of context for that decision
- [Automated tests for text](./observations/automated-tests-for-text.md) *(note)* — Text artifacts can be tested with the same pyramid as software — deterministic checks, LLM rubrics, corpus compatibility — built from real failures not taxonomy
- [Stale indexes are worse than no indexes](./observations/stale-indexes-are-worse-than-no-indexes.md) *(note)* — An agent trusts an index as exhaustive — a missing entry doesn't trigger search, it makes the note invisible
- [Template areas field nudges index updates](./observations/template-areas-field-nudges-index-updates.md)
- [Topic links from frontmatter are deterministic](./observations/topic-links-from-frontmatter-are-deterministic.md) *(note)* — The areas-to-Topics mapping is mechanical — now implemented as scripts/sync_topic_links.py
- [Two kinds of navigation](./observations/two-kinds-of-navigation.md) *(note)* — Link-following is local with context; search is long-range with titles/descriptions; indexes bridge both modes
- [Retrieval needs a metadata-aware scoring layer](./retrieval-scoring-layer.md) *(note)* — Metadata-aware reranking over semantic search — type-dependent recency decay, per-note overrides, SQLite index rebuilt from frontmatter
- [Scenarios](./scenarios.md) *(note)* — Concrete use cases for the knowledge system — upstream change analysis and proposing our own changes
- [Text testing framework — source material](./text-testing-framework.md) *(note)* — Reference framework for automated text testing — contracts per document type, test pyramid (deterministic/LLM rubric/corpus), production workflow
- [Three-space agent memory maps to Tulving's taxonomy](./three-space-agent-memory-maps-to-tulving-taxonomy.md) — Agent memory split into knowledge, self, and operational spaces mirrors Tulving's semantic/episodic/procedural distinction
- [Three-space memory separation predicts measurable failure modes](./three-space-memory-separation-predicts-measurable-failure-modes.md) — The three-space memory claim is testable because flat memory predicts specific cross-contamination failures
- [Title as claim enables traversal as reasoning](./title-as-claim-enables-traversal-as-reasoning.md) *(note)* — When note titles are claims rather than topics, following links between them reads as a chain of reasoning — the file tree becomes a scan of arguments, and link semantics (since, because, but) encode relationship types
- [What cludebot teaches us](./what-cludebot-teaches-us.md) — Techniques from cludebot worth borrowing — what we already cover, what to adopt now, and what to watch for as the KB grows
- [What doesn't work](./what-doesnt-work.md) *(review)* — Anti-patterns and areas with insufficient evidence — auto-commits, queue overhead, validation ceremony, session rhythm
- [What works](./what-works.md) *(review)* — Patterns proven valuable in practice — prose-as-title, template nudges, frontmatter queries, semantic search via qmd, discovery-first, public/internal boundary
