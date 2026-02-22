---
description: Index of notes about linking — how links work as decision points, navigation modes, link contracts, and automated link management
type: index
status: current
---

# Links

Links are the edges of the knowledge graph. Every link is a decision point for the reader: follow or skip? The quality of surrounding context determines whether that decision is informed or blind.

## Observations

- [agents-navigate-by-deciding-what-to-read-next](./observations/agents-navigate-by-deciding-what-to-read-next.md) — links, skills, and index entries are all contextual hints for read/skip decisions
- [two-kinds-of-navigation](./observations/two-kinds-of-navigation.md) — link-following is local with context; search is long-range with titles/descriptions; indexes bridge both
- [topic-links-from-frontmatter-are-deterministic](./observations/topic-links-from-frontmatter-are-deterministic.md) — the areas-to-Topics mapping is mechanical, now automated (outdated — see ADR)
- [stale-indexes-are-worse-than-no-indexes](./observations/stale-indexes-are-worse-than-no-indexes.md) — a missing index entry suppresses search; the note becomes invisible

## Decisions

- [001-generate-topic-links-from-frontmatter](./adr/001-generate-topic-links-from-frontmatter.md) — replace LLM-generated Topics footers with deterministic script

## Reference material

- [link-contracts-framework](./link-contracts-framework.md) — framework for systematic, testable linking: link contracts, intent taxonomy, agent implications
