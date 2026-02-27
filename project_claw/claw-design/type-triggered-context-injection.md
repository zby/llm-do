---
description: Document types could trigger automatic context injection — definitions loaded once per session when first referenced, retrieval profiles varying by type. This extends document affordances from what-you-can-do-with-it to what-gets-loaded-alongside-it.
type: note
traits: []
areas: [claw-design]
status: speculative
---

# Type-triggered context injection

## The problem

An agent reads a note that links to [crystallisation](../notes/crystallisation.md). The link is referential — "as defined in [crystallisation]" — and the definitional note exists precisely to pin down how the term is used in this project. But since [agents are stateless](./agent-statelessness-makes-skill-layers-architectural-not-pedagogical.md), the agent doesn't know the definition unless it follows the link. And following a link costs a tool call, context space, and a decision — overhead that makes agents less likely to look up definitions they "should" already know.

The result: definitions exist but don't reliably reach the agent that needs them. The knowledge is in the KB but not in the context window.

## The mechanism: type as retrieval trigger

If the harness knows a document's type, it can decide what to load alongside it. When an agent reads a document containing a link to a `definition`-typed note, the harness could auto-inject that definition into context — without the agent needing to follow the link explicitly.

This extends [document affordances](./document-types-should-be-verifiable.md) from "what operations can I perform on this document" to "what context gets loaded alongside this document." The type becomes a retrieval trigger, not just a structural assertion.

### Definitions as the first case

Definitions are the cleanest case for type-triggered injection because:

- **They're small.** Under 200 characters in the description, a few paragraphs in the body. The context cost is low.
- **They're stable.** Definitions change rarely. Once loaded, they remain valid for the session.
- **They're referential, not argumentative.** You don't need to evaluate a definition — you need to have it available. Auto-injection matches the link semantics: "as defined in" doesn't require the agent to decide whether to follow the link.
- **They should be loaded once per session.** A definition doesn't need re-reading. The harness could track which definitions have been injected and skip duplicates — paying the context cost once, not on every reference.

This would make definitions behave like imported constants in a programming language: declared once, available everywhere in scope.

### The `definition` type

For the harness to identify definitions, they need a machine-readable type. The current three definitional notes ([crystallisation](../notes/crystallisation.md), [stabilisation](../notes/stabilisation.md), [distillation](../notes/distillation.md)) are `type: note`. A `type: definition` would:

- Signal the harness to auto-inject on first reference
- Assert checkable structural properties: has examples, has negative examples ("Not X:"), links to sibling definitions, bounded length
- Make the title convention (topical) part of the type contract — definitions are a recognized exception to [title-as-claim](./title-as-claim-enables-traversal-as-reasoning.md)
- Prevent unbounded growth — a definition that needs Evidence/Reasoning/Caveats is really a `structured-claim` about the term, not a definition

### Other type-triggered behaviors

The mechanism isn't limited to definitions. Different types could trigger different retrieval profiles:

| Type | Triggered behavior | Rationale |
|------|-------------------|-----------|
| `definition` | Auto-inject on first reference, once per session | Vocabulary must be present for correct reasoning |
| `index` | Preload when entering a topic area | Navigation context reduces dead-end traversals |
| `adr` | Surface when modifying related code | Decisions constrain implementation; must be visible |
| `spec` | Load when implementing related features | Specs define the contract |

Each row is a hypothesis about what context is needed when. The harness tests these hypotheses by observing whether auto-injection improves agent outcomes vs. explicit loading.

## Connection to the loading hierarchy

The [context-loading strategy](./context-loading-strategy.md) currently describes a static hierarchy: CLAUDE.md (always) → skill descriptions (always) → skill bodies (on invoke) → task-specific docs (on demand). Type-triggered injection adds a dynamic layer: documents loaded reactively based on what the agent is reading.

This sits between "always loaded" and "on demand" — call it "on reference." The agent doesn't request the definition; the harness provides it. The agent doesn't need to know the definition exists; the type ensures it arrives.

The hierarchy becomes:
1. **Always** — CLAUDE.md, skill descriptions
2. **On reference** — definitions (first time), related ADRs, relevant indexes
3. **On invoke** — skill bodies
4. **On demand** — methodology notes, source reviews

## Why this requires our own harness

On Claude Code, the agent decides what to read. There's no interception point between "agent sees a link" and "agent follows the link." Auto-injection requires a harness that:

1. Parses the document being loaded
2. Identifies links to typed documents
3. Resolves those links and checks the target's type
4. Injects appropriate content before returning the document to the agent

This is straightforward to build but impossible on someone else's runtime. It's one of the concrete reasons to eventually port the claw to llm-do's own harness.

## Open questions

- **Context budget:** Even small definitions add up. With 20 technical terms, auto-injecting all on first reference might cost 4-5K tokens. Is that worth it? Probably yes for definitions (they're the vocabulary), but the budget question sharpens for larger types.
- **Staleness:** If a definition is injected once per session and later updated during the session, the agent has the stale version. Definitions are stable enough that this is unlikely, but ADRs or specs might not be.
- **Granularity:** Should the harness inject the full definition note or just the description? For definitions, the description might suffice. For ADRs, you probably want the full decision.
- **Discovery:** Auto-injection helps when the agent reads a document that links to a definition. But what about when the agent writes a response using a term it doesn't link to? That requires term detection, not just link detection — a harder problem.

---

Relevant Notes:
- [document types should be verifiable](./document-types-should-be-verifiable.md) — foundation: types assert checkable structural properties; this note extends affordances from operations to retrieval
- [instructions are typed callables](../notes/instructions-are-typed-callables.md) — parallel: that note gives skills type signatures; this note gives documents retrieval profiles
- [agent statelessness makes skill layers architectural](./agent-statelessness-makes-skill-layers-architectural-not-pedagogical.md) — motivates: the agent can't remember definitions, so the harness must provide them
- [context-loading strategy](./context-loading-strategy.md) — extends: adds an "on reference" layer between "always loaded" and "on demand"
- [title-as-claim-enables-traversal-as-reasoning](./title-as-claim-enables-traversal-as-reasoning.md) — context: definitional notes are an identified exception to claim titles; the `definition` type would formalize this

Topics:
- [claw-design](./claw-design.md)
