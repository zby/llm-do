---
description: Comparable knowledge/agent systems tracked for evolving ideas, convergence signals, and borrowable patterns
type: index
---

# Related Systems

External systems doing similar work — knowledge management for AI agents, context engineering, structured note-taking. We track these not just to borrow ideas but to watch how they evolve. Convergence across independent projects is a stronger signal than any single design argument.

## Systems

- [OpenClaw](./openclaw.md) — the category-defining claw: a personal AI assistant gateway that owns messaging surfaces, session lifecycle, and tool orchestration; reveals what "claw" means as a system category and where knowledge-system claws diverge from agent-gateway claws
- [Agent Skills for Context Engineering](./agent-skills-for-context-engineering.md) — skill-based context engineering reference library loaded as agent guidance; strong on operational patterns, no learning theory
- [Ars Contexta](./arscontexta.md) — Claude Code plugin that generates knowledge systems from conversation; ancestor of our claw, upstream source for link semantics and title-as-claim. Includes the "Agentic Note-Taking" article series (@molt_cornelius) — first-person agent testimony from inside the system
- [Thalo](./thalo.md) — custom plain-text language with grammar, types, validation, and LSP; makes the same programming-theory bet we do but with full compiler formalization
- [ClawVault](./clawvault.md) — TypeScript memory system with scored observations, session handoffs, and reflection pipelines; has a working workshop layer where we have theory, strongest source of borrowable patterns for ephemeral knowledge

## Patterns Across Systems

All six systems (including ours) independently converge on:
- **Filesystem over databases** — plain text, version-controlled, no lock-in
- **Progressive disclosure** — load descriptions at startup, full content on demand
- **Start simple** — architectural reduction outperforms over-engineering
- **Markdown as native format** — both for persistence and for LLM consumption

The divergences are more revealing:
- **Grounding discipline** — cognitive psychology (arscontexta) vs programming theory (claw, thalo) vs empirical operational patterns (Agent-Skills, OpenClaw)
- **Formalization level** — custom DSL (thalo) vs YAML conventions (claw) vs prose instructions (Agent-Skills, OpenClaw)
- **System scope** — knowledge system (claw, thalo, arscontexta) vs agent gateway (OpenClaw) vs memory pipeline (ClawVault) vs skill library (Agent-Skills)
- **Learning theory** — explicit (claw) vs implicit/none (all others)
- **Self-referentiality** — only our claw is simultaneously a knowledge system and a knowledge base about knowledge systems

## Open Questions

- Does convergence on filesystem-first indicate a durable pattern, or a phase that will be outgrown?
- Will the programming-theory grounding produce better systems than the psychology grounding, or will they converge?
- Are there systems we're missing that take a fundamentally different approach?
