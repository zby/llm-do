---
description: Simon's definition — learning is any change that produces a more or less permanent change in a system's capacity for adapting to its environment. All KB improvements are learning, from typo fixes to methodology changes.
type: note
traits: [has-claim, has-external-sources]
status: seedling
areas: []
---

# Learning is capacity change

Herbert Simon: "Learning is any change in a system that produces a more or less permanent change in its capacity for adapting to its environment." By this definition, almost every KB improvement is learning — even fixing a typo increases adaptive capacity because the system can now answer a question it would have confused before. The distinction isn't between "content change" and "capacity change" — all content changes improve capacity. The distinction is **how widely the improvement generalises**.

## The generalisation spectrum

| Change | Scope | Example |
|--------|-------|---------|
| Fix a typo | One retrieval | System can now match a query it would have missed |
| Sharpen a description | One note's findability | All queries that might match this note work better |
| Add a connection | Two notes' mutual discoverability | Navigation between these ideas now exists |
| Define structured sections for a type | All future notes of that type | Every related-system note gets consistent structure |
| Discover a design principle | All future decisions in that area | "Types and directories are orthogonal" applies broadly |
| Improve methodology | All future KB operations | The crystallisation gradient changes how everything stabilises |

Every row increases the system's adaptive capacity. The rows differ in how many future situations benefit.

## Argyris's loops as scope markers

Argyris's [single-loop vs double-loop learning](https://infed.org/dir/welcome/chris-argyris-theories-of-action-double-loop-learning-and-organizational-learning/) maps onto this spectrum as rough regions, not a binary:

- **Single-loop** — correcting errors within existing rules. Fixing notes, improving descriptions, adding missing links. The governing variables (types, conventions, methodology) don't change. Narrow generalisation scope.
- **Double-loop** — changing the governing variables themselves. Discovering that [types and directories are orthogonal](../claw-design/types-and-directories-are-orthogonal.md), developing the [crystallisation gradient](./crystallisation-is-continuous-learning.md), redesigning the [methodology enforcement approach](../claw-design/methodology-enforcement-is-stabilisation.md). Wide generalisation scope.

[Process crystallisation](./crystallisation-is-continuous-learning.md) (prompt → schema → code) sits in between — it doesn't change what the system knows but makes existing operations more reliable and cheaper, increasing capacity for the same class of tasks.

## Why this matters for the learning loop

The [KB learning loop](../claw-design/kb-learning-loop-is-an-open-problem.md) frames the open problem as needing automated mutations (extract, split, synthesise, relink, retire). These mutations span the whole spectrum:

- **Extract, reformulate** — narrow scope. Improving individual notes.
- **Relink, regroup, synthesise** — medium scope. Changing how knowledge connects.
- **Retire, restructure** — wide scope. Changing the system's organising principles.

Automating narrow-scope improvements is relatively tractable (ingest pipelines, LLM extraction, validation scripts). Automating wide-scope improvements is the hard part — it requires judgment about what principles generalise. This is why the learning loop is an open problem: the most valuable mutations are the widest-scope ones, and scope of generalisation is the hardest thing to assess automatically.

## Sources

- Herbert Simon: "Learning is any change in a system that produces a more or less permanent change in its capacity for adapting to its environment."
- Chris Argyris: [Single-loop vs double-loop learning](https://infed.org/dir/welcome/chris-argyris-theories-of-action-double-loop-learning-and-organizational-learning/) — single-loop corrects within existing rules; double-loop changes the governing variables.
- [Knowledge acquisition](https://en.wikipedia.org/wiki/Knowledge_acquisition) — extracting and structuring knowledge from sources; one region on the learning spectrum, not a separate activity.
