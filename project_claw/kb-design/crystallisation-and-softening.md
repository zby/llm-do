---
description: KB artifacts exist on a spectrum from calculator-like (exact, durable) to vision-feature-like (plausible theory, may soften) — design for both
type: note
traits: [has-claim]
areas: [kb-design]
status: current
---

# KB design must account for softening

The [bitter lesson boundary](../notes/bitter-lesson-boundary.md) distinguishes two kinds of crystallised artifacts: calculator-like (spec fully captures the problem) and vision-feature-like (spec encodes a theory that scale may outperform). Both exist in this KB. Practical systems are always hybrids, and the mix shifts over time through crystallisation and its complement, softening.

## What this means for the KB

Some KB artifacts are calculators — the sync scripts, the frontmatter schema, the link verification gates. Their specs fully define the problem. These are durable.

Others are vision features — the ingestion pipeline stages, the connection methodology, the three-phase discovery process. These encode our current theory of how knowledge work should be decomposed. They work now, but a more capable model might handle them as a single undifferentiated step.

Design implications:

- **Keep the two kinds separable.** Don't tangle durable infrastructure (file formats, index rebuilding) with decomposition theories (pipeline stages, skill boundaries). When a theory-artifact softens, you want to replace it without rewiring the infrastructure.

- **Spec what, not how.** The [retrieval scoring layer](./retrieval-scoring-layer.md) specifies *what* scoring should achieve (type-dependent recency decay) without prescribing *how* — that's a calculator-like spec. A skill that prescribes "first do X, then Y, then Z" is a vision-feature-like spec.

- **Watch for composition failure.** If skills don't compose into better outcomes, that's the softening signal — the decomposition is wrong, not the individual pieces.
