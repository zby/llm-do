---
description: Claude Code plugin that generates knowledge systems from conversation, backed by 249 research claims. Ancestor of our claw — we run a local instance but have diverged significantly in structure and theory.
type: note
status: current
areas: [related-systems]
last-checked: 2026-02-25
---

# Ars Contexta

A Claude Code plugin that generates complete knowledge systems from conversation. You describe how you think and work; the engine derives a cognitive architecture — folder structure, context files, processing pipeline, hooks, templates — tailored to your domain and backed by 249 research claims about tools for thought.

**Repository:** https://github.com/agenticnotetaking/arscontexta
**Local instance:** `arscontexta/` (stale — references old paths like `docs/notes/` instead of `project_claw/notes/`)

## Core Ideas

**Derivation, not templating.** The central claim is that every configuration choice should trace to specific research. The `/setup` flow asks 2-4 questions, maps signals to eight configuration dimensions with confidence scoring, then generates everything. This contrasts with template-based systems where you pick a preset.

**Three-space architecture.** Every generated system separates into: `self/` (agent persistent mind — identity, methodology, goals), `notes/` (knowledge graph), `ops/` (operational coordination — queue, sessions, observations). Names adapt to domain but the separation is invariant.

**The 6 Rs pipeline.** Extends Cornell Note-Taking's 5 Rs with a meta-cognitive layer: Record → Reduce → Reflect → Reweave → Verify → Rethink. Each phase has a distinct skill. The pipeline is the operational spine.

**Fresh context per phase.** Each processing phase spawns a fresh subagent to avoid attention degradation. The `/ralph` orchestrator reads the queue, spawns a subagent per task, parses the handoff, advances the phase. This is an explicit response to the context degradation problem that [Agent-Skills-for-Context-Engineering](./agent-skills-for-context-engineering.md) documents theoretically.

**Research-grounded decisions.** The `methodology/` directory contains 249 interconnected claims synthesising Zettelkasten, Cornell Note-Taking, Evergreen Notes, PARA, GTD, cognitive science (extended mind, spreading activation), network theory (small-world topology), and agent architecture. Every kernel primitive includes `cognitive_grounding` linking to specific research.

**Self-evolution through friction.** Observations (friction signals) and tensions (contradictions) accumulate during work. When thresholds are hit (10+ observations, 5+ tensions), `/rethink` triggers triage. The system grows at pain points, not before.

## Our Relationship

Arscontexta is the **ancestor** of our claw. We installed it, used its pipeline, and learned from its approach. Over time we diverged:

- **We built our own theory.** [Crystallisation](../stabilisation-is-learning.md), [oracle strength](../oracle-strength-spectrum.md), [methodology enforcement as stabilisation](../../claw-design/methodology-enforcement-is-stabilisation.md) — these emerged from our own work and have no counterpart in arscontexta's research graph.
- **We simplified the structure.** Arscontexta's three-space architecture (self/notes/ops) felt over-engineered for our use. We collapsed to a flatter `project_claw/` with notes, adr, sources, claw-design, tasks. No separate identity/methodology/goals files.
- **We developed verifiable document types.** Our [document classification](../../claw-design/document-classification.md) with types, traits, and status is structurally richer than arscontexta's template-with-schema approach. Types mark affordances; traits are independently checkable.
- **We developed link contracts.** Our [link contracts framework](../../claw-design/link-contracts-framework.md) and [title-as-claim](../../claw-design/title-as-claim-enables-traversal-as-reasoning.md) convention have no equivalent in arscontexta's linking model.
- **The local instance is stale.** It references `docs/notes/` and `docs/adr/` paths that no longer exist. Expected to be rewritten or retired.

## What Arscontexta Does Better

- **Research backing.** 249 claims with provenance is more systematic than our approach of deriving theory from practice. We tend to notice patterns and write notes; they start from established cognitive science.
- **Automation infrastructure.** Four hooks (session orient, write validate, auto commit, session capture) provide more operational automation than we currently have. Our skills are manually invoked.
- **Processing queue.** Their `queue.json` with phase tracking, priority, and `/next` recommendations is more structured than our task system.
- **Fresh context per phase.** The subagent-per-phase pattern is a concrete solution to attention degradation that we haven't implemented.

## What We Do Better

- **Learning theory.** We have a framework for understanding *when* to stabilise and *when* to keep things stochastic. Arscontexta has a fixed pipeline; we have a theory about pipeline evolution.
- **Document affordances.** Our type system tells agents what they can do with a document before reading it. Arscontexta treats all notes as structurally similar.
- **Lighter weight.** Our system works without hooks, queues, or session management. A claw is markdown files, skills, and CLAUDE.md. Lower barrier, less infrastructure to maintain.

## The Theoretical Bet

The deepest divergence is in grounding discipline. Arscontexta draws on **cognitive psychology** — spreading activation, generation effect, context-switching cost (Leroy 2009), extended mind thesis. We draw on **programming language theory** — [types mark affordances](../instructions-are-typed-callables.md), verifiability gradients, stabilise/soften as compilation, [the bitter lesson boundary](../bitter-lesson-boundary.md). [Thalo](./thalo.md) independently validates the programming-theory side by building a full compiler for knowledge management — Tree-Sitter grammar, typed entities, 27 deterministic validation rules — pushing formalization further than we do. The implicit bet: knowledge systems for LLM agents are closer to programming (formal, compositional, verifiable) than to human cognition (associative, affective, embodied). Time will tell which foundation produces better systems — or whether they converge.

## What to Watch

- Does arscontexta develop learning theory (crystallisation-like concepts)?
- How does the plugin marketplace model evolve — does it become a distribution channel for knowledge system patterns?
- Do the 249 research claims get maintained and updated, or become stale?
- Does the fresh-context-per-phase pattern prove its value in practice, and should we adopt it?

Topics:
- [related-systems](./related-systems-index.md)
