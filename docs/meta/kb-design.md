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

- [scenarios](./scenarios.md) — concrete use cases the knowledge system must serve
- [note-types](./note-types.md) — taxonomy of the type field for docs/notes/ frontmatter

## Observations

- [template-areas-field-nudges-index-updates](./observations/template-areas-field-nudges-index-updates.md) — structural prompts in templates beat procedural rules in documentation
- [links-are-decision-points](./observations/links-are-decision-points.md) — surrounding context must let the reader judge whether to follow a link
- [two-kinds-of-navigation](./observations/two-kinds-of-navigation.md) — link-following is local; search is long-range; indexes bridge both
- [topic-links-from-frontmatter-are-deterministic](./observations/topic-links-from-frontmatter-are-deterministic.md) — the areas-to-Topics mapping is mechanical, now automated
- [automated-tests-for-text](./observations/automated-tests-for-text.md) — text can be tested with the same pyramid as software

## Reference material

- [link-contracts-framework](./link-contracts-framework.md) — source framework for systematic, testable linking
- [text-testing-framework](./text-testing-framework.md) — source framework for automated text quality checks
