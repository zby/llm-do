---
description: Structural prompts in templates (like areas: []) are more reliable than procedural rules in documentation — they're present at the moment of action
type: insight
areas: [kb-design]
status: current
---

# Template areas field nudges index updates

When a note template includes an `areas: []` field, agents writing notes from that template naturally check which index to add the note to. The empty array is a prompt — it asks a question the agent has to answer.

The CLAUDE.md instructions say "every note should be linked from at least one index," but that's a rule agents can forget. The template field is different: it's in the agent's face at the moment of creation. The agent fills in title, description, then hits `areas: []` and thinks "which index?" That's the nudge.

This is a general pattern: **structural prompts in templates are more reliable than procedural rules in documentation.** The template is read at the moment of action. The documentation is read (maybe) at session start and then forgotten.

This observation triggered the creation of `docs/kb-design/` — it was a valuable insight about how knowledge systems work, but it had no natural home. It wasn't a design note about llm-do. It wasn't an ADR. It was a meta-observation about the system itself.

Topics:
- [kb-design](./../kb-design.md)
