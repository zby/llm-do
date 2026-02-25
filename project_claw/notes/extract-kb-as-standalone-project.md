# Extract KB as standalone project

The knowledge base in `project_claw/` should be extracted into its own project. The KB is the "source code" and the skills we produce are the "compiled programs" — users could use just the skills to build their own claws, or contribute to the general KB.

## Audience

People building agentic systems — how to structure agents, where the LLM ends and code begins, how to make agents reliable, how to compose them.

## Naming

Working name: **agentic-architecture**

Rejected alternatives:
- "neuro-symbolic knowledge base" — wrong audience. Neuro-symbolic in AI research means combining neural nets with formal symbolic reasoning (logic programming, ontologies, theorem provers). Our work is about engineering systems where LLMs and conventional software collaborate — crystallisation, bitter lesson boundary, stabilisation patterns.
- "agentic architecture knowledge base" — "knowledge base" describes format not content, adds noise to the name
- "agentic patterns" — viable but less distinctive
- "claw patterns" — requires too much context to understand

## Content scope

What the KB covers:
- Where to draw the boundary between LLM and code (bitter lesson boundary)
- How to progressively harden fluid LLM behavior into stable software (crystallisation)
- Patterns for agent orchestration, tool design, approval systems
- The claw as a genre — reactive AI-native knowledge systems
- Practical methodology for building hybrid LLM+code systems

## Skills alone won't work (yet)

Skills encode *how* to do KB work (ingest, connect, validate) but not *why* to make particular judgments. The quality of connections depends on understanding crystallisation, bitter lesson boundary, what makes a good note — knowledge that lives in the notes, not the skills.

However, skills don't need to reference the KB directly during execution. The value flows indirectly: once connections are established between notes, those connections surface relevant KB knowledge when the LLM reads connected notes in context. The KB teaches through its structure, not by being consulted as a reference.

This means the KB and skills need to ship together — the skills are the KB's interface, not a standalone product.

## Open questions

- What stays in llm-do vs moves to the new project? The llm-do-specific notes (code reviews, ADRs about llm-do internals) stay. General principles and claw methodology move.
- Do skills live in the new project or remain project-local? Skills are the "compiled" output — arguably they belong with the KB that produces them.
- How to handle the split without breaking links?
