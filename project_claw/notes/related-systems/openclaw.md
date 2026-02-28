---
description: The category-defining claw — a personal AI assistant gateway that owns messaging surfaces, session lifecycle, and tool orchestration; reveals what "claw" means as a system category and where knowledge-system claws diverge from agent-gateway claws
type: note
areas: [related-systems]
status: current
last-checked: 2026-02-28
---

# OpenClaw

**The personal AI assistant that gave the category its name.** A self-hosted gateway that connects to real messaging surfaces (WhatsApp, Telegram, Slack, Discord, Signal, iMessage, and more), routes inbound messages to an LLM-backed agent with tools (shell, browser, canvas, memory, cross-channel messaging), and replies through the same channel. The user interacts as if messaging a person.

**Repository:** https://github.com/openclaw/openclaw
**Status:** v2026.2.27, TypeScript/Node ≥22, MIT license, ~52 source directories, 41 extension packages, 54 bundled skills. Sponsored by OpenAI and others. The [Karpathy "Claws" post](../../sources/simon-willison-karpathy-claws.md) crystallised the category name from this project.

## Core Ideas

**The gateway as singleton control plane.** One long-lived daemon owns all channel connections, session state, tool execution, and memory. Everything routes through it — clients (CLI, macOS app, WebChat, mobile nodes) are thin viewers over WebSocket. No client holds session state; token counts, history, and routing are gateway-owned. This is a hard architectural invariant: "One Gateway per host." The trade-off is a single point of failure in exchange for a single source of truth.

**Workspace as agent personality.** The agent's identity and memory are defined by a directory of markdown files injected into the system prompt at session start:

| File | Purpose |
|------|---------|
| `AGENTS.md` | Operating instructions and accumulated memory |
| `SOUL.md` | Persona, tone, boundaries |
| `TOOLS.md` | User-maintained tool notes |
| `IDENTITY.md` | Name, emoji, vibe |
| `USER.md` | User profile, preferred forms of address |
| `BOOTSTRAP.md` | One-time first-run ritual (self-deletes after) |
| `MEMORY.md` | Curated long-term memory |

This is a [crystallisation](../../claw-design/claw-learning-is-broader-than-retrieval.md) of the agent's contextual competence into persistent files. The self-deleting `BOOTSTRAP.md` is particularly elegant — a one-shot initialization artifact that consumes itself on completion, a clean example of [workshop-layer](../../claw-design/a-functioning-claw-needs-a-workshop-layer-not-just-a-library.md) thinking applied to onboarding.

**Memory as plain markdown with vector overlay.** The radical simplicity choice: memory is just `MEMORY.md` (curated, injected at session start) plus `memory/YYYY-MM-DD.md` daily logs (accessed on demand via search tools). No proprietary format, no database as source of truth. A SQLite-backed vector index with hybrid BM25+cosine search, temporal decay, and MMR re-ranking is built *over* the markdown — the files remain the source of truth, the index is a derived acceleration structure.

**Pre-compaction memory flush.** When context approaches the compaction threshold, OpenClaw runs a silent agentic turn that prompts the model to write durable notes to disk before the context is summarised. The user never sees this turn. This elegantly solves context death at compaction boundaries — the model gets a dedicated opportunity to persist what matters before the window compresses. Properties: one flush per compaction cycle, silent (NO_REPLY convention), skipped when workspace is read-only.

**Skills as prompt indirection.** Skills are listed in the system prompt as (name, description, file path) but not loaded. The model `read`s the `SKILL.md` on demand. This keeps base prompt token cost bounded regardless of installed skill count (~24 tokens per skill plus field lengths), at the cost of one extra tool call per novel skill use. Load-time gating filters skills by required binaries, env vars, config keys, and OS platform — the agent never sees skills it can't use.

**Prompt cache stability through timezone-only time.** The system prompt includes only the timezone, never a dynamic timestamp. The model calls `session_status` when it needs the current time. This keeps the prompt prefix cache-stable across turns — a practical optimisation that trades one extra tool call for significant inference cost savings.

**Session key scoping as privacy architecture.** DM sessions can be scoped from shared (`main` — all DMs in one session) to fully isolated (`per-account-channel-peer`). The default shared scope is explicitly called out as a security risk: "Alice's private medical context can leak to Bob." The scoping levels aren't convenience features — they're a privacy architecture with real security implications for multi-user setups.

**Plugin slots for exclusive categories.** Memory plugins use a slot system — only one memory backend can be active. This prevents subtle correctness bugs from competing backends without requiring complex conflict resolution. A simple mechanism that avoids a hard problem.

## Comparison with Our System

OpenClaw and our claw operate at different levels of the stack. OpenClaw is an **agent gateway** — it orchestrates channels, sessions, tools, and model providers. Our claw is a **knowledge system** — it accumulates, connects, and learns from persistent notes. Both are "claws" in Karpathy's sense, but they solve different problems.

| Dimension | OpenClaw | Our Claw |
|-----------|----------|----------|
| Primary function | Agent gateway + personal assistant | Knowledge system + design workspace |
| Runtime | Standalone daemon, owns channel connections | Plugin to Claude Code, uses its runtime |
| Session model | JSONL transcripts, compaction, pruning | Claude Code's built-in context management |
| Memory format | Markdown files + vector index | Markdown files + qmd index |
| Context loading | Bootstrap file injection + on-demand skill reads | CLAUDE.md router + progressive disclosure |
| Learning mechanism | Agent writes to MEMORY.md and daily logs | Human-curated notes + agent-learnings |
| Agent identity | SOUL.md, IDENTITY.md, USER.md | CLAUDE.md conventions + skill descriptions |
| Scale | ~100K LOC, 41 extensions, 54 skills, 13+ channels | ~2K LOC runtime, ~200 notes, 12 skills |

**Where we align:**

- **Markdown as source of truth.** Both systems use plain markdown files as the canonical store, with search indexes as derived structures. Neither locks knowledge into a database.
- **Progressive disclosure.** OpenClaw lists skills but doesn't load them; our CLAUDE.md routes to task-specific docs. Both avoid frontloading everything into context. Both pay per-use tool-call costs for this.
- **Filesystem over databases.** Both treat the filesystem as the primary persistence layer. This is a convergence signal across the [entire related-systems set](./related-systems-index.md).

**Where we diverge:**

**Scope of "context."** OpenClaw's context is the agent's working state — conversation history, tool results, injected files. Our context is the accumulated knowledge base — notes, decisions, connections, indexes. OpenClaw optimises for *using* context within a session; we optimise for *building* context across sessions. These are complementary, not competing, concerns.

**Learning theory.** OpenClaw has no explicit theory of how the system learns. The agent writes to `MEMORY.md` and daily logs, but there's no framework for promotion, no maturity ladder, no concept of crystallisation. Memory accumulates through agent writes; it's curated through human editing of `MEMORY.md`. Our [document classification](../../claw-design/document-classification.md), [wikiwiki principle](../../claw-design/wikiwiki-principle-lowest-friction-capture-then-progressive-refinement.md), and [learning-as-crystallisation](../agentic-systems-learn-through-three-distinct-mechanisms.md) framework address exactly this gap — how knowledge moves from raw capture to durable, structured insight. OpenClaw has the usage volume to need this and doesn't have it; we have the theory and don't yet have the usage volume.

**Agent identity vs system identity.** OpenClaw gives the agent a *persona* — soul, name, emoji, user profile, speaking style. The agent is meant to feel like a person you're messaging. Our system gives the agent *instructions* — conventions, routing tables, quality checks. The agent is meant to feel like a skilled collaborator. These reflect genuinely different product visions: personal assistant vs research partner.

**Context loading strategy.** OpenClaw injects bootstrap files into the system prompt and trusts the agent to navigate from there. Our [context-loading-strategy](../../claw-design/context-loading-strategy.md) makes the routing table itself the primary injected content, with task-specific docs loaded on demand. OpenClaw's approach is more front-loaded (identity + memory injected every session); ours is more navigational (routing table injected, content pulled as needed). The bootstrap injection caps (20K chars/file, 150K total) suggest OpenClaw has hit the cost-of-frontloading problem in practice.

**Session persistence model.** OpenClaw owns its own JSONL session persistence with compaction, pruning, and maintenance. We delegate session management entirely to Claude Code. This is a consequence of the different runtime models — OpenClaw needs to manage sessions because it's a standalone daemon; we don't because Claude Code handles it.

## Borrowable Ideas

**1. Pre-compaction memory flush (ready to borrow).** The silent agentic turn before compaction is the single most elegant mechanism in the system. It solves a problem we'll face as sessions get longer: important in-context knowledge lost to compaction. The implementation is simple (a triggered silent turn with a "write what matters" prompt, one per compaction cycle) and the trade-off is clean (one extra LLM call per compaction). If Claude Code exposes compaction hooks, this pattern should be adopted.

**2. Bootstrap file taxonomy (partially borrowable).** The separation of instructions (AGENTS.md), identity (SOUL.md, IDENTITY.md), user context (USER.md), and tools context (TOOLS.md) is a useful decomposition. Our CLAUDE.md currently mixes instructions, routing, and conventions. We wouldn't want the persona-oriented files (SOUL.md, IDENTITY.md), but separating routing instructions from user-specific context from tool guidance could reduce CLAUDE.md's scope and improve cache stability. The question is whether this decomposition earns its file count.

**3. Skills gating by prerequisites (borrowable concept).** The load-time filtering of skills by required binaries, env vars, and config keys is clean. An agent never sees a skill it can't use. Our skills don't currently gate on prerequisites — if `qmd` isn't installed, the skill is still visible but will fail at runtime. Gating metadata in skill descriptions would prevent wasted tool calls.

**4. Self-deleting bootstrap artifacts (interesting pattern).** `BOOTSTRAP.md` exists only for the first session and is deleted after. This is a concrete instance of [workshop-layer](../../claw-design/a-functioning-claw-needs-a-workshop-layer-not-just-a-library.md) thinking — an artifact whose value is consumed by use. We don't have an equivalent, but the pattern could apply to onboarding workflows or one-time setup tasks.

**5. Prompt cache stability techniques (worth adopting).** Timezone-only time in system prompts (with `session_status` for dynamic time) is a small optimisation with real cost impact. Any always-loaded content that changes between turns should be examined for cache-busting effects.

## What We Should Not Borrow

**The gateway architecture.** OpenClaw's singleton daemon model is designed for always-on messaging — a fundamentally different runtime model from Claude Code sessions. Borrowing gateway patterns would be architecture tourism.

**The persona model.** SOUL.md and IDENTITY.md reflect a "personal assistant" product vision. Our system works best when the agent is a competent tool-user, not a character. Adding persona files would add complexity without serving our use case.

**The memory system's lack of structure.** OpenClaw's memory is pure append-to-markdown. No types, no promotion, no maturity ladder. This works when the primary consumer is a single user's personal assistant (low curation overhead), but would be a regression from our type system and learning theory.

## What to Watch

- **Does unstructured memory scale?** As OpenClaw users accumulate months of daily logs and `MEMORY.md` grows, does the lack of structure become a bottleneck? If OpenClaw eventually adds structure (categories, promotion, archival), the patterns they discover will be empirically grounded.
- **How do skills evolve?** OpenClaw has 54 bundled skills plus ClawHub for community skills. Watch whether the skill model stays as prompt indirection or evolves toward more structured skill-agent contracts. Their [gating metadata](../../claw-design/context-loading-strategy.md) is already richer than ours.
- **Category convergence.** OpenClaw defines the "claw" category — always-on agent with messaging, tools, persistence. As the category matures, watch whether knowledge-system claws (like ours) and agent-gateway claws (like OpenClaw) converge or remain distinct species. The [Karpathy framing](../../sources/simon-willison-karpathy-claws.md) — "orchestration, scheduling, context, tool calls and a kind of persistence" — is broad enough to encompass both, but the operational requirements are very different.
- **Pre-compaction flush effectiveness.** Does the silent memory-flush turn actually capture important context? This is testable — compare session quality before and after flush. If OpenClaw publishes data on this, it validates or invalidates the pattern for us.

---

Relevant Notes:
- [context-loading-strategy](../../claw-design/context-loading-strategy.md) — contrasts: OpenClaw injects bootstrap files and skill lists; we inject a routing table and load content on demand — both use progressive disclosure but with different front-loading strategies
- [a-functioning-claw-needs-a-workshop-layer](../../claw-design/a-functioning-claw-needs-a-workshop-layer-not-just-a-library.md) — extends: OpenClaw's self-deleting BOOTSTRAP.md and pre-compaction flush are concrete workshop-layer artifacts (value consumed by use), but the system has no theory of workshop vs library
- [claw-learning-is-broader-than-retrieval](../../claw-design/claw-learning-is-broader-than-retrieval.md) — contrasts: OpenClaw stores preferences, procedures, and identity as workspace files (SOUL.md, USER.md, MEMORY.md) but has no framework for how these evolve — the action-oriented knowledge types exist without a learning theory
- [simon-willison-karpathy-claws](../../sources/simon-willison-karpathy-claws.md) — foundation: OpenClaw is the system that gave the category its name; Karpathy's "orchestration, scheduling, context, tool calls and persistence" description applies
- [ClawVault](./clawvault.md) — sibling: both are claw-category systems; ClawVault formalised memory lifecycle (observations, handoffs, reflections), OpenClaw kept memory unstructured and focused on gateway orchestration — different bets on where complexity should live
- [document-classification](../../claw-design/document-classification.md) — contrasts: OpenClaw's workspace files (SOUL, IDENTITY, USER, AGENTS, TOOLS, MEMORY) are an implicit type system for agent context; our classification system covers knowledge artifacts rather than agent configuration

Topics:
- [related-systems](./related-systems-index.md)
