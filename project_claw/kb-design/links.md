---
description: Index of notes about linking — how links work as decision points, navigation modes, link contracts, and automated link management
type: index
status: current
---

# Links

Links are the edges of the knowledge graph. Every link is a decision point for the reader: follow or skip? The quality of surrounding context determines whether that decision is informed or blind.

## Foundations

- [title-as-claim-enables-traversal-as-reasoning](../notes/title-as-claim-enables-traversal-as-reasoning.md) — claim titles make link traversal read as reasoning; explains why "since [X]" works but "see [X]" is a different link intent, and where the pattern breaks for multi-claim documents

## Observations

- [agents-navigate-by-deciding-what-to-read-next](./observations/agents-navigate-by-deciding-what-to-read-next.md) — links, skills, and index entries are all contextual hints for read/skip decisions
- [two-kinds-of-navigation](./observations/two-kinds-of-navigation.md) — link-following is local with context; search is long-range with titles/descriptions; indexes bridge both
- [topic-links-from-frontmatter-are-deterministic](./observations/topic-links-from-frontmatter-are-deterministic.md) — the areas-to-Topics mapping is mechanical, now automated (outdated — see ADR)
- [stale-indexes-are-worse-than-no-indexes](./observations/stale-indexes-are-worse-than-no-indexes.md) — a missing index entry suppresses search; the note becomes invisible

## Decisions

- [001-generate-topic-links-from-frontmatter](./adr/001-generate-topic-links-from-frontmatter.md) — replace LLM-generated Topics footers with deterministic script

## Analysis

- [backlinks](./backlinks.md) — use cases for inbound link visibility: hub identification, source-to-theory bridging, impact assessment, tension surfacing; four design options with trade-offs

## Reference material

- [link-contracts-framework](./link-contracts-framework.md) — framework for systematic, testable linking: link contracts, intent taxonomy, agent implications

---

Agent Notes:
- 2026-02-24: added Foundations section with title-as-claim-enables-traversal-as-reasoning. The note belongs here because it's fundamentally about link semantics: "since [X]" vs "see [X]" is the distinction between argumentative and referential links, which determines how links function as reasoning connectors. The link-contracts-framework's intent taxonomy is the systematic version of what this note describes for inline prose links. Together with agents-navigate, these form a chain: title-as-claim explains WHY claim titles work -> agents-navigate explains HOW agents use that signal -> link-contracts provides the RULES for maintaining link quality.
