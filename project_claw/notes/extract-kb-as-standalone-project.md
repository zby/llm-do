---
description: Extraction plan for the claw system as a standalone repo with two tiers — derived artifacts only (skills, templates, scripts) for operational use, and derived+methodology for understanding, adaptation, and skill maintenance
type: note
traits: []
areas: [claw-design]
status: current
---

# Extracting the claw system requires a two-tier derivation model

The claw system in `project_claw/` should be extracted into its own repository. The core insight shaping the extraction: the operational layer (skills, templates, scripts) is *derived* from the methodology KB, and this derivation relationship is the organizing principle for both the repo structure and the distribution model.

## The derivation relationship

The entire operational layer — skills, templates, scripts — is derived from the methodology. The specific transformation varies:

- **Skills**: [distilled](../claw-design/skills-distil-methodology-not-crystallise-it.md) (prose → prose). Operational procedures extracted from discursive reasoning across methodology notes. Same medium, no phase change — just purification.
- **Templates**: distilled (prose → prose). Required sections and structural scaffolds derived from methodology about what makes good notes, what properties should be verifiable, what supports agent traversal.
- **Scripts**: crystallised (prose → code). The derivation crosses the natural-language→executable boundary — the phase transition that skills and templates don't undergo.

"Derived" is the umbrella term — it's neutral about the transformation type and just says "this came from the methodology." Distillation and crystallisation describe *how* the derivation happens: distillation stays in the same medium (prose → prose), crystallisation crosses into a different one (prose → code).

This means the source repo contains two layers: the methodology (source) and everything derived from it. Users can install either the derived layer alone or both layers.

## Two tiers

**Tier 1 — derived artifacts only (skills + templates + scripts):** "I want to build a KB for my project."
- Operational capability without the theory
- Works for common cases, but since [agent statelessness makes skill layers architectural](../claw-design/agent-statelessness-makes-skill-layers-architectural-not-pedagogical.md), there's a cliff when the procedures don't cover a case — the agent degrades into a generic LLM, not into a "less certain claw-augmented agent"
- Provenance links stripped at build time (dead weight without the methodology)

**Tier 2 — derived artifacts + methodology:** "I want to understand, adapt, and maintain the system."
- Two audiences:
  1. **System builders** developing similar knowledge systems — the methodology goes deep into first principles (files-not-database, progressive refinement, context loading, document classification)
  2. **KB refiners** improving their local claw — skills can't contain full knowledge, and when they hit edge cases, the methodology provides the reasoning to adapt
- Provenance links preserved — the agent can follow them on demand when procedures don't cover a situation
- Also serves as the "development environment" for evolving the derived artifacts themselves — you can't improve the distillate without access to the source, or the crystallised script without understanding the methodology it encodes

The tiers aren't "basic vs premium" — they're "operational vs maintainable."

## Build-time generation

[Skills should be generated at build time, not parameterised](../claw-design/generate-instructions-at-build-time.md). This applies to the full operational layer:

- **Path resolution**: Templates contain `{{claw_root}}/notes/`; the setup script resolves to the actual path (e.g., `project_claw/notes/` when embedded in a parent project, `./notes/` when standalone)
- **Provenance inclusion**: A single build configuration knob — Tier 1 strips provenance links, Tier 2 keeps them. Same source templates, two outputs.
- **The canonical form is standalone** (paths relative to claw root). Embedding in a parent project is the special case that requires a prefix.

Provenance links in source templates serve double duty: documentation of the derivation relationship (for humans maintaining the methodology) AND optional runtime context for Tier 2 agents. Same artifact, two consumers.

## What moves vs what stays

**Moves to the claw repo:**
- `claw-design/` — the methodology KB
- `skills/` (connect, convert, ingest, snapshot-web, validate)
- `templates/` — referenced by skills, derived from methodology
- `scripts/` — index generation, topic sync, referenced by skills
- `WRITING.md` — writing guide is methodology, not project-specific
- General-methodology sources (Willison/Karpathy claws, Toulmin, Notes Without Reasons, arscontexta)

**Stays in llm-do:**
- `notes/` — mostly llm-do-specific design exploration
- `adr/` — llm-do architecture decisions
- `code-reviews/`, `tasks/` — llm-do project artifacts
- Project-specific CLAUDE.md sections and routing table

**Gray area — general theory notes:** Notes like `crystallisation-learning-timescales.md`, `bitter-lesson-boundary.md`, `agentic-systems-learn-through-three-distinct-mechanisms.md` are general concepts but also the core vocabulary the claw methodology uses. Options: (a) move them as foundational notes in the claw repo, (b) keep them in llm-do with cross-repo references, (c) let the methodology notes be self-contained enough to not need them. This needs a decision.

## How llm-do consumes the extracted claw

After extraction, llm-do installs the claw as Tier 2 (derived + methodology), because:
- It's the birthplace — developers need to evolve the methodology
- The methodology is a showcase for llm-do's own crystallisation concepts
- Several llm-do notes reference claw-design notes and vice versa

The CLAUDE.md Knowledge System section becomes a routing fragment that wires the installed claw into the project. The claw repo provides a template fragment; the project customizes it with local routing (where project-specific notes go, etc.).

## Naming

Working name: **claw** (distinctive, specific to the genre)

Previously considered:
- "agentic-architecture" — too broad, implies general agent design rather than the specific knowledge-system genre
- "neuro-symbolic knowledge base" — wrong audience (academic AI research, not engineering)
- "claw patterns" — requires too much context without prior exposure

## Open Questions

- Installation mechanism: git submodule (version-locked, easy for Tier 2) vs setup script (copies and generates, lighter for Tier 1) vs both?
- How to handle cross-repo references when methodology notes reference general-theory notes that stay in llm-do?
- Should the repo include an example/starter claw (empty KB structure with skills wired up) for new users?
- The CLAUDE.md fragment design — how much can be templated vs how much must be project-specific?

---

Relevant Notes:
- [skills distil methodology, not crystallise it](../claw-design/skills-distil-methodology-not-crystallise-it.md) — foundation: the distillation relationship (prose → prose derivation) that applies to skills and templates; scripts undergo the distinct crystallisation transformation
- [agent statelessness makes skill layers architectural](../claw-design/agent-statelessness-makes-skill-layers-architectural-not-pedagogical.md) — foundation: why the two tiers are permanent infrastructure, not a learning progression; explains the Tier 1 cliff
- [generate instructions at build time](../claw-design/generate-instructions-at-build-time.md) — enables: the build-time generation pattern that makes tier-specific output possible
- [context-loading strategy](../claw-design/context-loading-strategy.md) — constrains: the loading hierarchy the claw fragment must integrate into

Topics:
- [claw-design](../claw-design/claw-design.md)
