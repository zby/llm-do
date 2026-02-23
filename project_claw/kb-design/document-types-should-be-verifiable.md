---
description: Document types should assert verifiable structural properties, not subject matter — with a base type + traits model inspired by gradual and structural typing
type: note
traits: [has-claim]
areas: [kb-design]
status: current
---

# Document types should be verifiable

## The analogy

In programming, a type tells you what structural guarantees hold and what operations are valid. The language enforces these. In a knowledge base we have a more stochastic model — types are assigned by agents, not compilers — but the principle still applies: a type should assert something you can check.

## What passes the test

Types that assert verifiable structure:

- **spec** — has Motivation, Design, Implementation sections; detailed enough to build from
- **review** — references specific code/modules; has Findings; dated
- **insight** — title is a claim (a sentence, not a noun phrase); body is a short argument
- **index** — majority of content is navigational links

Each of these makes a structural promise you could verify — mechanically in some cases, with a rubric in others.

## What fails

**"design"** says nothing structural. A design note could be a spec, an exploration, a brainstorm, a proposal, or a comparison. It describes subject matter (this is about design), which is what the `areas` field is for. As a type it dominates the KB — half the notes are "design" — which means it does no discriminatory work.

Flat types like **"research"** and **"analysis"** also have fuzzy boundaries. Is a research note that reaches a crystallized conclusion an insight or research? Is an analysis that cites external sources research or analysis? Forcing a single choice from a flat enum loses information.

## Base types + traits

The solution borrows from object-oriented subtyping and structural typing. Instead of a flat enum, use a **base type** (hard structural category) plus **traits** (independently verifiable properties):

```yaml
type: note
traits: [has-claim, has-external-sources]
```

**Base types** are structurally distinct, low ambiguity:

| Base type | Structural test |
|-----------|----------------|
| `note` | Default — no structural claims |
| `spec` | Implementation-ready detail, has Design/Implementation sections |
| `review` | Examines specific existing code, has Findings, dated |
| `index` | Primarily navigational links |

**Traits** are independently checkable properties a note can satisfy in any combination:

| Trait | What it asserts | Verifiability |
|-------|----------------|---------------|
| `has-claim` | Title is an assertion, body argues for it | Requires judgment |
| `has-comparison` | Structured evaluation of alternatives | Grep for comparison tables |
| `has-external-sources` | Cites material outside the project | Grep for URLs/references |
| `has-implementation` | Contains code sketches or concrete API proposals | Grep for code blocks |

A note can satisfy multiple traits without conflict. What we called "research" is `note` + `has-external-sources`. What we called "insight" is `note` + `has-claim`. A research note with a crystallized conclusion is `note` + `has-external-sources` + `has-claim` — no forced choice.

## The honest default

**`note`** is the base type that makes no structural claim — like `Any` in a gradually typed language. New content enters as `note` and gets promoted to `spec`, `review`, or `index` as it gains structure. Traits are added as they become true.

This mirrors the [crystallisation gradient](../../docs/theory.md) applied to the KB itself:

1. New content enters as `type: note` (soft, no structural claims)
2. Traits accumulate as the document matures
3. Base type gets promoted to `spec` or `review` when hard structural criteria are met
4. A note that stays bare `note` with no traits for a long time is a signal — maybe it needs splitting, promotion, or review

## Programming language analogies for fuzziness

Our types are inherently fuzzy — assigned by agents and humans, not compilers. Mainstream type systems are designed to be crisp, but several concepts map to our situation:

**Gradual typing** (Python, TypeScript) is the closest fit for the crystallisation gradient. Start with `Any` (no structural claims), progressively add annotations as you gain confidence. The system works at every point on the spectrum. `note` is our `Any` — honest about making no claims.

**Protocols / structural typing** map to traits. A class satisfies a Protocol if it has the right methods, regardless of explicit declaration. A document satisfies `has-claim` if the title is an assertion — regardless of labeling. We store the label for searchability rather than re-checking every time.

**Refinement types** (`{x: int | x > 0}`) are types with predicates. Our traits are refinement predicates on `note`. The key property: some predicates are easy to check (`has-external-sources` — grep for URLs), others require judgment (`has-claim` — is the title an assertion?). This matches the varying verifiability of our traits.

**But there is no clean analogy for the fuzziness itself.** Programming types are crisp by design. The closest parallel is ML classifiers outputting probabilities — or **soft typing** from Scheme/Lisp, where the system infers types advisorily and violations are warnings, not errors.

## Design principle: tolerance of misclassification

Since types are fuzzy claims, not enforced contracts, the system must degrade gracefully when claims are wrong:

- Search by type should be "usually right", not "guaranteed complete"
- A note typed `spec` that's really an exploration is a quality issue, not a system failure
- The trait list is a best-effort annotation, not a contract
- Nothing should break if a type or trait is missing or incorrect

## Implications

- The [note-types taxonomy](./note-types.md) should be updated: replace the flat enum with base types + traits
- Existing notes typed `design` should be downgraded to `note` with appropriate traits
- Flat types `research`, `analysis`, `comparison` become trait combinations on `note`
- WRITING.md should document the verifiability principle and the tolerance-of-misclassification constraint
- Agents assigning types should ask: "what structural property am I asserting?" not "what is this about?"

Topics:
- [kb-design](./kb-design.md)
