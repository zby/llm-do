---
description: Instructions, skills, hooks, and scripts form a stabilisation gradient for methodology — from fully stochastic (LLM may follow) to fully deterministic (code always runs), with hooks occupying a middle ground of deterministic triggers with stochastic responses
type: note
traits: [has-claim]
areas: [claw-design]
status: seedling
---

# Methodology enforcement is stabilisation

The ways we enforce methodology in the KB — instructions, skills, hooks, scripts — map directly onto the [stabilisation spectrum](../../docs/theory.md). The enforcement layers parallel the [crystallisation verifiability gradient](../notes/crystallisation-learning-timescales.md) — where crystallisation moves code from prompt tweaks through schemas to deterministic modules, methodology enforcement moves practices from written guidance through structured skills to automated scripts. Each layer trades flexibility for reliability by moving the trigger, the response, or both from stochastic to deterministic.

| Layer | Trigger | Response | Reliability | Example |
|-------|---------|----------|-------------|---------|
| Instruction | stochastic (LLM remembers) | stochastic (LLM interprets) | lowest | "check descriptions" in CLAUDE.md |
| Skill | deterministic (user invokes) | stochastic (LLM executes) | medium | `/validate` checks note quality |
| Hook (warn) | deterministic (event fires) | stochastic (LLM acts on output) | medium-high | validate-note.sh outputs WARN on missing description |
| Hook (block) | deterministic (event fires) | deterministic (rejected) | high | exit 1 prevents the operation |
| Script | deterministic (user/hook runs) | deterministic (code runs) | highest | sync_topic_links.py rewrites Topics footer |

The key insight: hooks are not cleanly "deterministic." A hook that outputs a warning is a deterministic trigger with a stochastic response — the LLM decides what to do with the warning. Only blocking hooks (exit non-zero) are fully deterministic. This means the three-tier model (instruction → skill → hook) that arscontexta uses oversimplifies — the real picture is a gradient, which is just stabilisation.

## Maturation trajectory

This is [progressive compilation applied to methodology](../notes/programming-practices-apply-to-prompting.md) — new best practices should start stochastic and stabilise as they prove out:

1. **Instruction** — write it in CLAUDE.md or WRITING.md. Cheap to revise, tests whether the practice is worth encoding. If the LLM follows it inconsistently, that's signal.
2. **Skill** — encode it as a structured prompt. Reliable when invoked, but requires explicit invocation. Good for judgment-requiring operations that shouldn't be automated.
3. **Hook/script** — automate the deterministic parts. Only after the practice has stabilised enough that you know exactly what the check should do.

Not everything should complete the trajectory. Operations requiring semantic judgment (like "is this connection genuine?") belong permanently at the skill level. Attempting to automate judgment produces [confident systematic errors](./arscontexta-review.md) — the over-automation risk. The [topic-links-from-frontmatter case](./observations/topic-links-from-frontmatter-are-deterministic.md) is a clean example of the trajectory completing: an LLM-generated Topics footer was recognised as fully mechanical, and the operation moved to a deterministic script.

## Current state

We have hooks in `.claude/hooks/` but they aren't wired up (`"hooks": {}` in settings.json) and reference old paths. We have scripts that work (sync_topic_links.py, generate_notes_index.py). We have skills that work (validate, connect, ingest). We have instructions that work (CLAUDE.md, WRITING.md). The gradient exists — we just haven't needed to push anything further toward the deterministic end yet.

## Open questions

- When should a WRITING.md instruction become a validate check? What's the signal that instruction-level enforcement isn't enough?
- Should hook warnings be treated differently from skill output? The LLM sees both as text, but the trigger mechanism differs.
- Are there practices currently at skill level that should be scripts? (sync_topic_links.py was probably this — a skill-level operation that turned out to be fully deterministic.)

---

Relevant Notes:
- [arscontexta review](./arscontexta-review.md) — source: the doc-to-skill-to-hook trajectory idea, reframed here as stabilisation
- [crystallisation: the missing middle](../notes/crystallisation-learning-timescales.md) — grounds: the verifiability gradient for code (prompt tweaks -> schemas -> evals -> deterministic modules) is the general pattern this note instantiates for methodology
- [crystallisation is continuous learning](../notes/crystallisation-is-continuous-learning.md) — foundation: the stabilisation gradient for code; this note applies the same gradient to methodology
- [programming practices apply to prompting](../notes/programming-practices-apply-to-prompting.md) — synthesizes: the maturation trajectory is progressive compilation applied to methodology — flexible instructions frozen into rigid, efficient automation
- [topic links from frontmatter are deterministic](./observations/topic-links-from-frontmatter-are-deterministic.md) — exemplifies: a skill-level operation that completed the maturation trajectory into a deterministic script
- [what doesn't work](./what-doesnt-work.md) — examples: validation ceremony and session rhythm protocol as premature automation

Topics:
- [claw-design](./claw-design.md)
