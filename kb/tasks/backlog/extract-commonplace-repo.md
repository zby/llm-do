# Extract Commonplace as standalone repo

## Idea

Extract the claw system from `project_claw/` into its own GitHub repo named **commonplace**. The repo is both a claw (a reactive, AI-native knowledge system) and the methodology for building claws. It contains two layers: methodology (theory, design principles, claw-specific methodology) and derived artifacts (skills, templates, scripts) produced from it.

GitHub description: *A claw — a reactive, AI-native knowledge system — for building claws. Methodology, theory, and derived operational tools (skills, templates, scripts) for Claude Code agents.*

License: **CC BY 4.0** (Creative Commons Attribution). Mostly prose; attribution required, no share-alike constraint. Add LICENSE file manually since GitHub's picker doesn't include CC BY 4.0.

## Why

- The claw methodology is general — not llm-do-specific. Others can use it to build their own claws.
- Keeping it in llm-do buries the methodology inside a project it's outgrown.
- Extraction makes the derivation relationship (methodology → skills/templates/scripts) explicit and installable.

## Rough Scope

- **Create the commonplace repo** with CC BY 4.0 license
- **Move methodology:**
  - `claw-design/` — knowledge system methodology
  - Most of `notes/` — general theory and principles (crystallisation, stabilisation, bitter lesson boundary, etc.)
  - `docs/theory.md` content — general theory (probabilistic programs, distribution shaping, stabilise/soften); split out llm-do-specific sections (harness, hybrid VM implementation) which stay
  - General-methodology sources (Willison/Karpathy claws, Toulmin, Notes Without Reasons, arscontexta)
  - `WRITING.md`
- **Move derived artifact sources:**
  - `skills/` (connect, convert, ingest, snapshot-web, validate) — convert to Jinja2 templates with `{{claw_root}}` placeholders
  - `templates/` — note scaffolds
  - `scripts/` — index generation, topic sync
- **Keep in llm-do:**
  - llm-do-specific notes (runtime design, approval system, toolset state, PydanticAI integration, UI pipeline)
  - `adr/`, `code-reviews/`, `tasks/`
  - llm-do-specific sections of `docs/theory.md`
  - `docs/architecture.md`, `docs/reference.md`, `docs/cli.md` etc.
  - Project-specific CLAUDE.md sections
- **Build the installation step:**
  - Python script using Jinja2 to resolve templates into concrete skill files
  - Configuration: claw root path, which skills to install
  - Install into `.claude/skills/` of the target project
  - Generate CLAUDE.md fragment from template
  - Handle Python dependencies
- **Wire llm-do as a consumer:**
  - Add commonplace as git submodule (or decide on other inclusion mechanism)
  - Run installation step to generate skills
  - Update CLAUDE.md to use generated fragment
  - Fix any broken cross-references between llm-do notes and moved methodology

## Why Not Now

Nothing blocking — this is ready to activate when prioritised.

## Trigger to Activate

Decision to start the extraction work.
