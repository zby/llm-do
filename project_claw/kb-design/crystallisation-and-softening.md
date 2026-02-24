---
description: A KB's value is its ability to answer project questions — the learning loop and evaluation criteria are open problems
type: note
traits: [has-claim]
areas: [kb-design]
status: speculative
---

# The KB needs a learning loop

## What is a KB for?

A knowledge base exists to answer questions about the project. This defines value for every artifact: a note is valuable if it helps answer a question, a link is valuable if it helps navigate from a question to an answer, a grouping is valuable if it makes related answers findable together.

New knowledge — extracting claims, writing synthesis notes, discovering connections — is valuable only insofar as it improves future question-answering.

## Knowledge lives in both notes and links

A KB's knowledge is in the content of its notes and in the structure of its links — neither alone is sufficient. A note without links still says something. A link without good notes on both ends is useless. But the link structure is the part that's hardest to get right and most underinvested in: adding notes is easy, discovering which notes genuinely connect and why requires judgment.

This suggests that learning at scale for a KB involves improving both — better notes and better links — but that the link structure is where the most untapped value sits, because it's where understanding is encoded: which ideas support each other, which are in tension, which compose into larger arguments.

## The boiling cauldron (aspirational)

The visible KB is the production system. Learning could happen through a background process that continuously proposes mutations:

- **Extract**: pull a claim from a source that hasn't been extracted yet
- **Split**: break a note that makes two claims into two notes
- **Synthesise**: two notes that together imply something neither says alone
- **Relink**: find semantically similar notes that aren't linked
- **Reformulate**: improve a title so it works better as prose when linked
- **Regroup**: a cluster of notes suggests an index that doesn't exist yet

Each mutation would be speculative — staged separately, surfaced for human review only when it scores high enough.

## Open problems

**Evaluation.** The KB's value is defined by the questions it answers, but those questions evolve with the project. There's no static benchmark to optimise against. Eventually, logging actual usage (queries, failed retrievals, how many hops to an answer) could provide signal — but we don't have enough usage yet to learn from.

**Quality gates.** Structural metrics (PageRank, betweenness centrality, cluster density) are proxies at best. A note can be well-connected because it's vague enough to "relate to" everything. The real test is whether a change helps answer a question that couldn't be answered before — and we don't have a systematic way to measure that yet.

**Surfacing rate.** Too many proposals and the human ignores them. Too few and the system isn't learning. Calibrating this requires feedback on what gets accepted, which requires enough volume to learn from.

These are all instances of the same gap: **we need more usage before we can design the learning loop properly.** The right move for now is to keep building the KB manually, pay attention to what works and what doesn't, and revisit this when there's enough history to learn from.

## Connection to crystallisation

The [bitter lesson boundary](../notes/bitter-lesson-boundary.md) distinguishes calculator-like artifacts (spec captures the problem) from vision-feature-like artifacts (spec encodes a theory). The KB's infrastructure — file formats, frontmatter schema, sync scripts — is calculator-like. The knowledge organisation — which links exist, how notes are grouped, what gets extracted — is vision-feature-like. A learning loop would be the mechanism for continuously improving the vision-feature layer. We're not ready to build it, but the distinction tells us where it would operate.
