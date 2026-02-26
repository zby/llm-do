---
description: Three independent arguments for structured document types with LLMs — failure-mode transfer from human writing, activation of higher-quality training distributions, and readability for human reviewers
type: note
areas: [claw-design]
status: seedling
---

# Three arguments support structured document types for LLMs

Structured document types like `structured-claim` enforce specific sections (Evidence, Reasoning, Caveats) in the text body. There are three independent arguments for why this works with LLMs, each standing on its own.

## Argument 1: Human writing structures transfer because failure modes overlap

Human writing genres — Toulmin argumentation, scientific paper structure, legal brief format — evolved under selection pressure. They exist because they help humans avoid specific reasoning failures. The Toulmin scaffold, for instance, forces the writer to separate evidence from reasoning and to surface assumptions.

The naive transfer argument ("it helps humans, so it helps LLMs") is weak because LLMs are not humans. But it becomes stronger when we observe that LLMs exhibit surprisingly human-like failure modes: they get distracted by irrelevant context, they conflate evidence with opinion, they skip qualifications when the argument feels strong. These failures are "un-machine-like" — you wouldn't expect a computational system to get distracted — but they happen.

This overlap suggests a methodology: rather than assuming wholesale transfer, **evaluate the specific arguments for why a structure helps humans, and check whether each argument applies to LLMs.** For Toulmin, the argument is "separating evidence from warrant prevents conflation" — and LLMs do conflate evidence with warrant. For scientific paper structure, the argument is "methods sections enable reproducibility" — which may be less relevant for LLMs.

This is still speculative and would require empirical verification, but it's more principled than blind analogy.

## Argument 2: Structure activates higher-quality training distributions

LLMs are autoregressive — they produce text that continues the pattern in context. When the context contains sections like `## Evidence` and `## Reasoning`, the model's output will resemble the training data that had similar structure: scientific papers, legal analyses, peer-reviewed arguments. These documents are, on average, higher quality for reasoning purposes than the bulk of internet text.

The structure acts as a distribution selector. A free-form prompt might draw from blog posts, forum comments, or opinion pieces. A Toulmin-shaped template steers the model toward the subset of its training data where authors were already doing rigorous argumentation. We assume — reasonably — that scientific papers and formal arguments have better epistemic value for our purposes than unstructured web text.

## Argument 3: Structure helps humans read LLM output

Even if the LLM neither reasons better (Argument 1) nor produces better content through continuation (Argument 2), structured output is easier for humans to evaluate and critique. A claim with separated Evidence and Reasoning sections lets a reader check each independently — "are these facts right?" and "does this logic follow?" are easier questions than "is this essay correct?"

This argument doesn't depend on LLMs at all. It's purely about readability. Structured document types become a guarantee that LLM output arrives in a form amenable to human review.

## The arguments are independent and complementary

Each argument stands alone — any one of them justifies enforcing structure. Together they cover the full chain: the LLM might reason better (1), the output will be shaped better (2), and the human reader can evaluate it better (3).

---

Relevant Notes:
- [document-classification](../claw-design/document-classification.md) — context: the type system these arguments justify, particularly `structured-claim` as a base type with required sections
- [claim notes should use Toulmin-derived sections](../claw-design/claim-notes-should-use-toulmin-derived-sections-for-structured-argument.md) — foundation: the specific Toulmin structure this note argues works for LLMs
- [programming practices apply to prompting](./programming-practices-apply-to-prompting.md) — extends: adds a new category of transfer — not just programming practices but writing genre conventions

Topics:
- [claw-design](../claw-design/claw-design.md)
