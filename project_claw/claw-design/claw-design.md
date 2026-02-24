---
description: Index of notes about designing and building the knowledge base itself — what works, what doesn't, how to test it
type: index
status: current
---

# Claw design

How we design the knowledge base for llm-do's design history. These are meta-observations — not about llm-do the library, but about the system we use to track its evolution.

## Evaluation

- [what-works](./what-works.md) — proven patterns: prose-as-title, template nudges, frontmatter queries, discovery-first
- [what-doesnt-work](./what-doesnt-work.md) — anti-patterns and insufficient evidence: auto-commits, queue overhead
- [needs-testing](./needs-testing.md) — promising but unconfirmed: extract/connect/review cycle, input classification

## Foundations

- [files-not-database](./files-not-database.md) — files with git beat a database for agent KBs: universal interface, free versioning, zero infrastructure; derived indexes solve scale problems without replacing the source of truth
- [document-types-should-be-verifiable](./document-types-should-be-verifiable.md) — design rationale: types assert checkable structural properties, not subject matter; base type + traits model inspired by gradual typing
- [document-classification](./document-classification.md) — the spec implementing the above: base types, traits, migration from old flat types
- [scenarios](./scenarios.md) — concrete use cases the knowledge system must serve
- [context-loading-strategy](./context-loading-strategy.md) — CLAUDE.md should be a slim router, not a manual; match instruction specificity to loading frequency
- [title-as-claim-enables-traversal-as-reasoning](./title-as-claim-enables-traversal-as-reasoning.md) — claim titles make link traversal read as reasoning chains; topical titles break this, which is why multi-claim specs get different title conventions

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
- [arscontexta-review](./arscontexta-review.md) — curated extraction from arscontexta's ~250 methodology notes: description-as-retrieval-filter, falsifiability test for claims, doc-to-skill-to-hook maturation trajectory, automation retirement criteria, verbatim risk diagnostic

## Gaps

- [kb-learning-loop-is-an-open-problem](./kb-learning-loop-is-an-open-problem.md) — the KB needs a continuous improvement loop, but evaluation requires usage history we don't have yet. The boiling cauldron (extract/split/synthesise/relink/regroup mutations) is aspirational; what-works and what-doesnt-work serve as the manual observation log until we can design the loop properly.
- [claw-learning-is-broader-than-retrieval](./claw-learning-is-broader-than-retrieval.md) — extends the learning loop problem: a Claw's learning must improve action capacity (classification, planning, communication), not just retrieval. The retrieval-oriented framing is one layer; action-oriented learning needs different knowledge types (preferences, procedures, precedents) and different evaluation criteria.
- [retrieval-scoring-layer](./retrieval-scoring-layer.md) — speculative: metadata-aware reranking over qmd results. Now connected to files-not-database (derived index pattern), what-cludebot-teaches-us (staleness decay), three-space model (metabolic rates), and document-types-should-be-verifiable (type trustworthiness prerequisite). Promote to Foundations when/if validated.

---

Agent Notes:
- 2026-02-23: connected files-not-database to what-works, what-cludebot-teaches-us, and the koylanai source. The "files as source of truth, derived indexes" pattern is a thread that runs through most of the Foundations and Evaluation sections — it's the implicit architectural assumption the whole KB rests on. Making it explicit via the files-not-database note strengthens the foundations.
- 2026-02-23: connected retrieval-scoring-layer. Its core idea — per-type decay rates in retrieval — is anticipated by both cludebot (staleness decay) and the three-space model (metabolic rates). The note concretizes what those notes describe abstractly. Keeping in Gaps since it's still speculative, but it's well-grounded in existing thinking now.
- 2026-02-24: connected kb-learning-loop-is-an-open-problem. The note ties together much of the index: what-works/what-doesnt-work are the manual observation log the loop would feed from, needs-testing's extract/connect/review cycle is a primitive version of the boiling cauldron, retrieval-scoring-layer addresses part of the quality gates problem, and scenarios defines the evaluation criteria. The crystallisation-is-continuous-learning connection is the strongest — the learning loop is the aspirational automated version of the manual crystallisation cycle.
- 2026-02-24: connected title-as-claim-enables-traversal-as-reasoning. Added to Foundations — it's the theoretical grounding for why prose-as-title (listed in what-works as a proven pattern) actually works: claim titles make traversal read as reasoning chains, and the multi-claim boundary explains why specs get different title conventions. Bridges to the links index via link semantics (argumentative vs referential), agents-navigate (why cheap navigation decisions depend on claim titles), and context-loading-strategy (progressive disclosure's first layer).
- 2026-02-24: connected claw-learning-is-broader-than-retrieval. Added to Gaps alongside kb-learning-loop — it extends the learning loop problem by arguing retrieval is only one mode. Strongest new connection: koylanai's Personal Brain OS independently converges on the four knowledge types (preferences, procedures, precedents, voice) the note identifies as missing from retrieval-oriented KB design. The three-space failure modes note gets a reverse link because its predicted failures are exactly what happens when action-oriented knowledge is forced into retrieval-oriented structure. Document-classification connection raises an open question about whether current base types can accommodate action-oriented knowledge.
- 2026-02-24: connected arscontexta-review. Added to Reference material — it's a curated source review like link-contracts-framework and text-testing-framework, but covering a broader methodology collection. The strongest new connections are to programming-practices-apply-to-prompting (the Tier 1 ideas are instances of the general transfer pattern) and kb-learning-loop (productivity porn diagnostic as evaluation heuristic). The doc-to-skill-to-hook trajectory concretizes what crystallisation-is-continuous-learning describes abstractly for code — it's crystallisation applied to methodology, moving from written instructions through skills to automated hooks.
