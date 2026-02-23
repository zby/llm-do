---
description: Base types assert verifiable structure (note, spec, review, index, adr); traits assert independently checkable properties (has-claim, has-comparison, has-external-sources, has-implementation)
type: spec
areas: [kb-design]
status: current
---

# Note types

See [document-types-should-be-verifiable](./document-types-should-be-verifiable.md) for the design rationale.

## Base types

Base types are hard structural categories with low ambiguity. A document has exactly one base type.

| Base type | Structural test | Verifiability |
|-----------|----------------|---------------|
| `note` | Default — no structural claims | Always valid |
| `spec` | Implementation-ready detail; has Design/Implementation sections | Check for sections |
| `review` | Examines specific existing code; has Findings; dated | Check for code refs, date |
| `index` | Primarily navigational links | Check link density |
| `adr` | Architecture decision record; has Context/Decision/Consequences | Check for ADR sections |

`note` is the honest default — like `Any` in a gradually typed language. New content starts as `note` and gets promoted when it clearly satisfies a more specific base type.

## Traits

Traits are independently checkable properties. A document can have zero or more traits regardless of its base type. Stored in the `traits` frontmatter field as a list.

| Trait | What it asserts | Verifiability |
|-------|----------------|---------------|
| `has-claim` | Title is an assertion; body argues for it | Requires judgment |
| `has-comparison` | Structured evaluation of alternatives (tables, option lists) | Grep for comparison tables |
| `has-external-sources` | References material outside the project | Grep for URLs/citations |
| `has-implementation` | Contains code sketches or concrete API proposals | Grep for code blocks with API surface |

### What the old flat types become

| Old type | New encoding |
|----------|-------------|
| `design` | `note` (was subject matter, not structure) |
| `insight` | `note` + `has-claim` |
| `analysis` | `note` + `has-comparison` |
| `research` | `note` + `has-external-sources` |
| `comparison` | `note` + `has-comparison` |

## Frontmatter example

```yaml
---
description: Storing an LLM output collapses a distribution to a point
type: note
traits: [has-claim]
areas: [index]
---
```

## Design principles

**Types are fuzzy.** They are assigned by agents and humans, not compilers. The system must tolerate misclassification — nothing breaks if a type or trait is wrong. Types are search aids, not enforcement boundaries.

**Types are verifiable.** Each type and trait asserts a structural property you can check. The question is "what structural property am I asserting?" not "what is this about?" Subject matter belongs in `areas`.

**Types crystallise.** Notes start as `note` and get promoted as they gain structure. A bare `note` that persists is a signal for review. This mirrors the crystallisation gradient applied to the KB itself.

Topics:
- [kb-design](./kb-design.md)
