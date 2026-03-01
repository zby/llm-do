---
description: Extraction plan for the claw system as a standalone repo — what moves, what stays, how llm-do consumes it, and the installation step that generates derived artifacts from templates
type: note
traits: []
areas: [claw-design]
status: current
---

# Extracting the claw system into its own repo

The claw system in `project_claw/` should be extracted into its own repository. The repo contains two layers: the methodology (theory, design principles, claw-specific methodology) and artifacts derived from it (skills, templates, scripts). The derived artifacts are produced by an installation/build step that resolves templates into concrete files for the target project.

## What moves vs what stays

The boundary: everything more general than llm-do alone moves. Only llm-do-specific artifacts stay.

**Moves to the claw repo (methodology):**
- `claw-design/` — knowledge system methodology
- Most of `notes/` — general theory and principles (crystallisation, stabilisation, bitter lesson boundary, programming-practices-apply-to-prompting, oracle-strength-spectrum, etc.)
- `docs/theory.md` content — general theory of LLM-code hybrid systems (probabilistic programs, distribution shaping, stabilise/soften). Folds into methodology; the distinction between "theory" and "methodology" is artificial. The llm-do-specific sections (the harness, hybrid VM implementation details, tradeoffs) stay in llm-do.
- General-methodology sources (Willison/Karpathy claws, Toulmin, Notes Without Reasons, arscontexta)
- `WRITING.md` — writing guide is methodology, not project-specific

**Moves to the claw repo (derived artifact sources):**
- `skills/` (connect, convert, ingest, snapshot-web, validate) — as templates with `{{claw_root}}` placeholders
- `templates/` — note scaffolds, referenced by skills
- `scripts/` — index generation, topic sync

**Stays in llm-do:**
- llm-do-specific notes (runtime design, approval system, toolset state, PydanticAI integration, UI pipeline)
- `adr/` — llm-do architecture decisions
- `code-reviews/`, `tasks/` — llm-do project artifacts
- llm-do-specific sections of `docs/theory.md` (harness, hybrid VM implementation)
- `docs/architecture.md`, `docs/reference.md`, `docs/cli.md` etc. — llm-do public docs
- Project-specific CLAUDE.md sections and routing table

## How llm-do consumes the claw repo

After extraction, llm-do includes the claw repo (likely as a git submodule) and runs an installation step. The installation:

1. **Generates skills** from templates — resolves `{{claw_root}}` to the actual path (e.g., `project_claw/` when embedded in llm-do), producing concrete skill files in `.claude/skills/`. This follows the [generate-at-build-time](../claw-design/generate-instructions-at-build-time.md) pattern: the canonical form uses paths relative to the claw root; embedding in a parent project adds the prefix.

2. **Installs Python dependencies** — scripts may need libraries (e.g., for index generation). The claw repo would specify these, and the installation step ensures they're available.

3. **Generates a CLAUDE.md fragment** — the Knowledge System section that routes the agent to the right places. The claw repo provides a template; the project fills in local details (where project-specific notes go, what areas exist).

The result: llm-do has the full methodology available (for understanding, adapting, and maintaining the system) plus generated operational artifacts wired into the project.

## The installation step

Skills currently hardcode `project_claw/` paths throughout — in grep commands, script invocations, save targets. The [generate-at-build-time](../claw-design/generate-instructions-at-build-time.md) note already designs the solution: templates with placeholders resolved at setup time. The canonical skill form is standalone (relative paths like `./notes/`, `./scripts/`). Embedding adds the project-specific prefix.

The installation step is a script in the claw repo that:
- Takes a configuration (claw root path in the target project, which skills to install, any project-specific overrides)
- Generates concrete skill files from Jinja2 templates
- Copies or symlinks templates and scripts
- Checks Python dependencies

**Jinja2 for templating, not LLMs.** The template resolution is mechanical — substitute paths, include/exclude sections. There's no ambiguity that benefits from LLM judgment. This is exactly the kind of operation that should be crystallised: known behavior, deterministic, cheap, testable. Using an LLM would also require an API key just to install, which is terrible UX.

## Naming and license

Name: **commonplace** — as in "commonplace book," the historical practice of collecting and refining knowledge. The repo is both a claw and the methodology for building claws.

License: **CC BY 4.0** (Creative Commons Attribution). The repo is mostly prose (methodology notes, skills, templates); CC BY is designed for creative/written content. Attribution required, no share-alike constraint — people can install it, adapt it, build proprietary claws on top, but they credit the source.

GitHub description: *A claw — a reactive, AI-native knowledge system — for building claws. Methodology, theory, and derived operational tools (skills, templates, scripts) for Claude Code agents.*

Previously considered names:
- "claw" — taken by [OpenClaw](https://github.com/openclaw/openclaw) ecosystem
- "agentic-architecture" — too broad
- "lore" — taken by a [cross-agent memory SDK](https://github.com/amitpaz1/lore)
- "kiln", "cairn", "trellis" — all taken by AI projects

## Open Questions

- How to split `docs/theory.md` — clean cut between general theory and llm-do-specific sections, or rewrite the general parts as standalone methodology notes?
- Should the repo include a starter claw (empty KB structure with skills wired up) for new users?
- The CLAUDE.md fragment — how much can be templated vs how much must be project-specific?
- Git submodule vs other inclusion mechanism?

---

Relevant Notes:
- [skills distil methodology, not crystallise it](../claw-design/skills-distil-methodology-not-crystallise-it.md) — foundation: the distillation relationship (prose → prose derivation) that applies to skills and templates; scripts undergo the distinct crystallisation transformation
- [agent statelessness makes skill layers architectural](../claw-design/agent-statelessness-makes-skill-layers-architectural-not-pedagogical.md) — foundation: why the methodology and derived artifacts are permanent infrastructure, not a learning progression
- [generate instructions at build time](../claw-design/generate-instructions-at-build-time.md) — enables: the build-time generation pattern that the installation step implements
- [context-loading strategy](../claw-design/context-loading-strategy.md) — constrains: the loading hierarchy the CLAUDE.md fragment must integrate into

Topics:
- [claw-design](../claw-design/claw-design.md)
