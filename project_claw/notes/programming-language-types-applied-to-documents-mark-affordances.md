---
description: Programming-language type systems applied to knowledge base documents — types mark which operations are valid on content, not just what it's about
type: note
areas: []
status: speculative
---

# Programming-language types applied to documents mark affordances, not subjects

In programming, a type tells you what operations are valid on a value. `int` doesn't mean "this is a number" — it means you can add, compare, use as an index. The type determines what you *can do* with the data.

The same principle applies to document types in a knowledge base operated by agents. A type like `claim` isn't a subject-matter label — it marks a set of operations the document affords:

| Type | Afforded operations |
|------|-------------------|
| `claim` | verify, gather evidence, challenge, use as assumption for derived claims |
| `spec` | implement, test against requirements, review for completeness |
| `instructions` | follow, execute, validate steps |
| `question` | research, decompose, answer |
| `index` | navigate, check coverage, find gaps |

This is not about automatic execution. Just as `int` doesn't mean arithmetic happens — it means arithmetic is *valid* here — a document type marks what agents or humans *can meaningfully do* with that content.

## Connection to the hybrid VM

This extends the [stabilise/soften framework](../../docs/theory.md) into knowledge artifacts. The operations afforded by a type can themselves sit anywhere on the stochastic-deterministic spectrum:

- **Deterministic**: check whether all claims in an index have at least one linked evidence note
- **Stochastic**: judge whether gathered evidence actually supports a claim

The type is the interface; the operation's implementation can move between LLM and code as patterns stabilise — the same dynamic theory.md describes for tool implementations.

## Instructions as a type

`instructions` deserves special attention. Skills, tasks (active, backlog, recurring) — these are all documents whose primary affordance is *being followed*. A task is a procedure: prerequisites, goal, checklist of steps, verification plan. An agent picks it up and executes it. If the KB had skills as first-class documents, they'd carry this type too. It's the document equivalent of a callable: the content is a procedure, and the valid operation is execution.

## Why this matters

Without affordance-bearing types, a knowledge base is a pile of text that agents search and read. With them, agents can reason about *what to do* with a document before reading it — the type is a contract about valid operations, just as in a typed program.

The [verifiability criterion](../kb-design/document-types-should-be-verifiable.md) is the quality test: a type earns its place only if it asserts structural properties that enable specific operations. `type: design` fails because it affords nothing that `type: note` doesn't. `type: claim` succeeds because it enables verification workflows that generic notes don't support.

## Instructions should check argument types

If types mark valid operations, then instructions (skills, tasks, workflows) that operate on documents should declare which types they accept — the same way functions declare parameter types.

Currently KB operations take a path and hope for the best. `/connect` implicitly expects a note or index. `/ingest` expects a source file. A recurring review expects code paths. A verification workflow would expect a `claim`. None of them check.

With type annotations on instructions, you get early validation: "this document is an `index`, but this workflow operates on `claim` — wrong type." The instruction is a function, the document is an argument, and the document's type determines whether the operation is valid.

This also clarifies the `instructions` type from the other direction: instructions are callables that have signatures — they accept certain document types as input and produce certain types as output. A skill that takes a source and produces a `source-review` has a type signature: `source → source-review`.

## Open Questions

- What's the minimal set of types that covers the operations we actually perform?
- Should affordances be expressed as traits (composable) rather than types (exclusive)? A spec with a claim in it affords both implementation and verification.
- How do compound documents work — a note that contains both claims and questions?

---
Relevant Notes:
- [document types should be verifiable](../kb-design/document-types-should-be-verifiable.md) — foundation: establishes the verifiability criterion this note builds on
- [theory](../../docs/theory.md) — foundation: the stabilise/soften framework this extends to knowledge artifacts
