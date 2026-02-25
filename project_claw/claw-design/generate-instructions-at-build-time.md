---
description: LLM instructions with variable placeholders add per-invocation interpretation cost — generate concrete instructions at build time instead, paying the flexibility cost once
type: note
traits: [has-claim]
areas: [claw-design]
status: seedling
---

# Generate LLM instructions at build time, don't parameterise them

When a skill or CLAUDE.md instruction contains a variable like `{{claw_root}}`, every invocation requires the LLM to recognise the variable, look up its value, substitute mentally, then act on the result. Each substitution is trivial. But skills are read frequently — a connect skill might be invoked dozens of times across a project's lifetime, and each invocation has multiple substitution sites (grep commands, path arguments, example outputs). The cumulative cost isn't just tokens — it's an additional interpretation layer between reading and acting, and occasionally the LLM gets it wrong (forgetting to substitute, mangling a path).

Template generation eliminates this. A build-time step reads `SKILL.md.template`, replaces `{{claw_root}}` with `project_claw`, and writes a concrete `SKILL.md` that says `grep -r "term" project_claw/notes/` literally. The generated instruction is **direct** — no indirection between what the LLM reads and what it should do.

This is [stabilisation applied to configuration](./methodology-enforcement-is-stabilisation.md). The template is soft (flexible, parameterised); the generated output is hard (literal, concrete). The generation script is the crystallisation mechanism. You pay the flexibility cost once at generation time, not on every use.

The analogy to compiled vs interpreted code is exact: you *could* ship the template and interpret it at runtime, but the values are known at "compile" time. Generating is cheaper in every dimension that matters — simpler instructions, fewer failure modes, easier debugging (you can read the generated file and see exactly what the LLM will see).

## When this applies

The principle applies whenever:
- A value is **known at setup time** and doesn't change during operation (paths, project names, collection directories)
- The instruction is **read frequently** (always-loaded CLAUDE.md, commonly invoked skills)
- The LLM must **act on the value** (use it in commands, reference it in paths), not just understand it conceptually

It does NOT apply to values that genuinely vary at runtime (the current note being processed, a URL being ingested). Those remain parameters to the skill invocation.

## Implications for claw portability

This emerged from the claw extraction problem: skills in `project_claw/skills/` hardcode `project_claw/` paths dozens of times. Making the claw reusable requires either runtime variables or build-time generation. Since [CLAUDE.md is a router, not a manual](./context-loading-strategy.md) — always-loaded context should be slim and simple — adding variable interpretation mechanics to it is the wrong direction. Generate once, load the literal result every time.

The canonical form for skills is standalone (paths relative to claw root: `./notes/`, `./scripts/`). Embedding a claw in a parent project (like llm-do's `project_claw/`) is the special case that requires a path prefix. The generation step adds that prefix.

---

Relevant Notes:
- [methodology enforcement is stabilisation](./methodology-enforcement-is-stabilisation.md) — foundation: the stabilisation gradient from stochastic to deterministic; template generation is a specific instance of moving configuration from runtime interpretation to build-time resolution
- [CLAUDE.md is a router, not a manual](./context-loading-strategy.md) — motivates: always-loaded context should be slim; variable interpretation mechanics add complexity to every session
- [generate topic links from frontmatter](./adr/001-generate-topic-links-from-frontmatter.md) — exemplifies: an earlier case of the same move — replacing LLM-generated output with a deterministic build step

Topics:
- [claw-design](./claw-design.md)
