---
description: Index of notes about designing and building the knowledge base itself — what works, what doesn't, how to test it
type: index
status: current
---

# KB design

How we design the knowledge base for llm-do's design history. These are meta-observations — not about llm-do the library, but about the system we use to track its evolution.

## Evaluation

- [what-works](./what-works.md) — proven patterns: prose-as-title, template nudges, frontmatter queries, discovery-first
- [what-doesnt-work](./what-doesnt-work.md) — anti-patterns and insufficient evidence: auto-commits, queue overhead
- [needs-testing](./needs-testing.md) — promising but unconfirmed: extract/connect/review cycle, input classification

## Foundations

- [files-not-database](./files-not-database.md) — files with git beat a database for agent KBs: universal interface, free versioning, zero infrastructure; derived indexes solve scale problems without replacing the source of truth
- [document-types-should-be-verifiable](./document-types-should-be-verifiable.md) — design rationale: types assert checkable structural properties, not subject matter; base type + traits model inspired by gradual typing
- [note-types](./note-types.md) — the spec implementing the above: base types, traits, migration from old flat types
- [scenarios](./scenarios.md) — concrete use cases the knowledge system must serve
- [context-loading-strategy](./context-loading-strategy.md) — CLAUDE.md should be a slim router, not a manual; match instruction specificity to loading frequency

## Observations

- [template-areas-field-nudges-index-updates](./observations/template-areas-field-nudges-index-updates.md) — structural prompts in templates beat procedural rules in documentation
- [agents-navigate-by-deciding-what-to-read-next](./observations/agents-navigate-by-deciding-what-to-read-next.md) — links, skills, and index entries are all contextual hints for read/skip decisions
- [two-kinds-of-navigation](./observations/two-kinds-of-navigation.md) — link-following is local; search is long-range; indexes bridge both
- [topic-links-from-frontmatter-are-deterministic](./observations/topic-links-from-frontmatter-are-deterministic.md) — the areas-to-Topics mapping is mechanical, now automated
- [automated-tests-for-text](./observations/automated-tests-for-text.md) — text can be tested with the same pyramid as software
- [stale-indexes-are-worse-than-no-indexes](./observations/stale-indexes-are-worse-than-no-indexes.md) — a missing index entry suppresses search; the note becomes invisible
- [what-cludebot-teaches-us](./what-cludebot-teaches-us.md) — techniques from cludebot worth borrowing, what we already cover, and what to watch for at scale

## Decisions

- [001-generate-topic-links-from-frontmatter](./adr/001-generate-topic-links-from-frontmatter.md) — replace LLM-generated Topics footers with deterministic script

## Reference material

- [link-contracts-framework](./link-contracts-framework.md) — source framework for systematic, testable linking
- [text-testing-framework](./text-testing-framework.md) — source framework for automated text quality checks

## Gaps

- [retrieval-scoring-layer](./retrieval-scoring-layer.md) — speculative: metadata-aware reranking over qmd results. Now connected to files-not-database (derived index pattern), what-cludebot-teaches-us (staleness decay), three-space model (metabolic rates), and document-types-should-be-verifiable (type trustworthiness prerequisite). Promote to Foundations when/if validated.

---

Agent Notes:
- 2026-02-23: connected files-not-database to what-works, what-cludebot-teaches-us, and the koylanai source. The "files as source of truth, derived indexes" pattern is a thread that runs through most of the Foundations and Evaluation sections — it's the implicit architectural assumption the whole KB rests on. Making it explicit via the files-not-database note strengthens the foundations.
- 2026-02-23: connected retrieval-scoring-layer. Its core idea — per-type decay rates in retrieval — is anticipated by both cludebot (staleness decay) and the three-space model (metabolic rates). The note concretizes what those notes describe abstractly. Keeping in Gaps since it's still speculative, but it's well-grounded in existing thinking now.
