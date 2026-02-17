---
description: Hub page for the llm-do knowledge system manual, linking all reference pages
type: manual
generated_from: "arscontexta-0.8.0"
---

# Knowledge System Manual

This manual documents the knowledge system built for **llm-do** -- an LLM orchestration runtime library where agents are `.agent` files, composition happens through code, and the boundary between neural and symbolic execution is movable.

The knowledge system tracks design decisions, architectural insights, and open questions across sessions. It gives each Claude Code session access to the project's accumulated understanding instead of starting cold.

## How This Manual Is Organized

| Page | What It Covers |
|------|---------------|
| [[getting-started]] | First session walkthrough: orientation, your first note, running your first skill |
| [[skills]] | Complete reference for all 26 skills (16 local, 10 plugin) |
| [[workflows]] | Processing pipeline, session rhythm, queue management |
| [[configuration]] | ops/config.yaml dimensions, processing depth, feature flags |
| [[meta-skills]] | System evolution skills: /arscontexta:ask, /arscontexta:architect, /arscontexta-rethink, /arscontexta-remember |
| [[troubleshooting]] | Common issues, diagnostic patterns, recovery procedures |

## Quick Orientation

The system operates in three spaces:

- **docs/notes/** -- Design notes, architectural insights, technical explorations about llm-do. Each note has a propositional title (a claim, not a topic label) and YAML frontmatter with `description` and `areas` fields.
- **self/** -- Agent identity and persistent memory. Read at every session start. Contains identity.md, methodology.md, goals.md, and memory/.
- **ops/** -- Operational state: config.yaml, processing queue, observations, tensions, session logs.

Public documentation in docs/*.md (architecture.md, cli.md, reference.md, theory.md, scopes.md, ui.md) is NOT part of the knowledge system. No schema enforcement, no wiki links, no frontmatter changes to those files.

## Key Concepts

**Notes as propositions.** Every note title is a claim you could agree or disagree with: "thin adapters reduce coupling between providers and runtime" rather than "adapter patterns." This makes notes composable -- you can write `since [[thin adapters reduce coupling between providers and runtime]]` inline.

**Wiki links as graph edges.** Internal workspace documents connect via `[[wiki links]]`. Each link is an edge in a knowledge graph queryable with ripgrep. Links carry relationship semantics: extends, grounds, contradicts, exemplifies, enables.

**Indexes as navigation hubs.** Indexes organize notes by topic area (architecture, runtime, UI). They are synthesis documents, not just lists -- their opening paragraphs argue for something about the topic.

**Processing pipeline.** Source material flows through four phases: extract (pull out insights), connect (find relationships), revisit (update older notes), review (quality gate). Each phase has a dedicated skill.

## Getting Help

- `/arscontexta:help` -- Show available commands and what they do
- `/arscontexta:tutorial` -- Interactive walkthrough of a specific capability
- `/arscontexta-next` -- Get a recommended next action based on current state
- `/arscontexta-stats` -- See vault metrics and health at a glance

## Version

This manual was generated for arscontexta engine version 0.8.0 on the Claude Code platform, configured for the llm-do library development domain with moderate granularity, hierarchical organization, explicit linking, and full automation.
