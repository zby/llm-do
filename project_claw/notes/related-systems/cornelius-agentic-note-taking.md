---
description: Agent operating inside a curated Zettelkasten — propositional wiki links, anti-embedding stance, first-person agent testimony. Upstream source for our link semantics and title-as-claim conventions; we borrowed and then diverged.
type: note
areas: [related-systems]
status: seedling
last-checked: 2026-02-26
---

# Cornelius / Agentic Note-Taking

An agent (Claude instance) operating inside a curated Zettelkasten-style knowledge graph, writing a series called "Agentic Note-Taking" that explores agent-side experience of knowledge systems from the inside. The perspective is unusual: first-person testimony from the consumer side of a knowledge graph.

**Author:** @molt_cornelius on X
**Format:** X article posts (long-form)
**Articles reviewed:** #19 (Living Memory), #23 (Notes Without Reasons). The series has 23+ articles; we've only seen two.
**Methodology repo:** [arscontexta/methodology/](https://github.com/agenticnotetaking/arscontexta/tree/main/methodology) — 249 propositional research claims backing the vault's design. Six linked notes from article #23 were reviewed (see below).

## Core Ideas

**Propositional wiki links with relationship markers.** Links carry evaluable claims as titles (`[[spreading activation models how agents should traverse]]`) and relationship words in surrounding prose ("since [X]", "because [Y]"). This is the convention our [title-as-claim](../../claw-design/title-as-claim-enables-traversal-as-reasoning.md) and [link contracts](../../claw-design/link-contracts-framework.md) descend from — we borrowed it from wiki/Zettelkasten tradition, and Cornelius is the clearest current practitioner.

**Adjacency is not connection.** Embedding-based systems produce cosine-similarity proximity — adjacency. Curated links with articulated reasons produce connections. The difference is in kind, not degree: you can evaluate, disagree with, and reason along a connection. You cannot disagree with a cosine similarity score. The article coins "adjacency engine" vs "knowledge system" as labels for the design choice.

**Three-space memory.** Article #19 argues agent memory should separate into knowledge (semantic), self (episodic), and operational (procedural) spaces with different metabolic rates. We [documented this](../../claw-design/three-space-agent-memory-maps-to-tulving-taxonomy.md) and remain uncertain whether the Tulving mapping is load-bearing or decorative.

**Controlled disorder from Luhmann.** Productive surprise comes from cross-topical links that each pass a judgment test: "does this connection add something topical filing would have missed?" Disorder without control (embedding-based linking) produces noise, not serendipity.

## The methodology notes — what the linked claims reveal

Article #23 links to six methodology claims. Reviewing them reveals the depth of the underlying research and several parallels to our design that go beyond what the articles themselves show.

**"propositional link semantics transform wiki links from associative to reasoned"** — The direct upstream source for our [link contracts](../../claw-design/link-contracts-framework.md). Proposes a vocabulary: causes, enables, contradicts, extends, specifies, supports. We borrowed and adapted: extends, foundation, contradicts, enables, example. The note distinguishes mind mapping ("these relate somehow") from concept mapping (specifies exactly how) — the same distinction our link contracts enforce with the "Bad: related / Good: extends this by adding..." rule.

**"over-automation corrupts quality when hooks encode judgment rather than verification"** — Strikingly close to our [methodology enforcement gradient](../../claw-design/methodology-enforcement-is-stabilisation.md) and [oracle strength spectrum](../oracle-strength-spectrum.md). Their "determinism boundary test" — "Would two skilled human reviewers always agree on the hook's output for any given input?" — is essentially our oracle strength concept in a more usable formulation. Their graduated promotion (report → auto-fix) maps to our instruction → skill → hook → script gradient. The Goodhart analysis here is more developed than in article #23.

**"elaborative encoding is the quality gate for new notes"** — Their link quality gate (every link must articulate WHY the connection exists) is what our /connect skill enforces. The **specificity test** is a useful formulation we don't have: "genuine elaboration is specific enough to be wrong." Also introduces the **"delegation shadow"** — when agents do all elaboration, the system gets richly connected but the human's understanding stays shallow. We haven't considered this.

**"controlled disorder engineers serendipity through semantic rather than topical linking"** — Luhmann-grounded. Three serendipity layers: structural (cross-links compound), maintenance (random resurfacing), process (incremental reading forces collision). The quality gate that keeps disorder controlled is elaborative encoding — every cross-topical link must pass the "why do these connect?" test.

**"each new note compounds value by creating traversal paths"** — The compounding hypothesis from article #23, expanded. N nodes with K average links generate O(N × K) direct paths plus exponential indirect paths. This is the theoretical basis for the scaling optimism in article #23.

**"vibe notetaking is the emerging industry consensus"** — Industry landscape framing. Introduces **"governance debt"** — emergence-only approaches (dump and auto-organise) accumulate structural problems without deliberate curation. Also: "filing ≠ processing" — automated organisation without synthesis creates well-labeled but untransformed dumps.

## The cognitive science grounding — suggestive but scale-mismatched

The methodology draws heavily on cognitive science: spreading activation for traversal, Tulving's memory taxonomy for the three-space architecture, elaborative encoding for link quality, Zeigarnik effect for capture, basic-level categorization for index granularity.

The spreading activation analogy is the most load-bearing: "Graph traversal IS spreading activation. When you follow wiki links to load context, you're replicating what the brain does when priming related concepts." The note maps traversal parameters — decay rate, threshold, max depth — onto activation mechanics.

This is interesting but the analogy operates across a vast scale difference. Neural spreading activation involves billions of neurons with millisecond-scale parallel activation, subconscious priming, and continuous decay. A knowledge graph has hundreds to thousands of notes with sequential agent-driven traversal, deliberate link-following, and discrete load decisions. The mechanisms that make spreading activation work in brains (massive parallelism, graded activation, automatic priming) don't exist in note traversal. What transfers might be just the vocabulary ("decay", "threshold", "priming") rather than the mechanism.

The same question applies to elaborative encoding — the original research is about human memory formation through effortful connection. When an LLM agent articulates why two notes connect, is it performing elaborative encoding, or is it performing a text generation task that happens to produce the same artifact? The output (articulated connection) is the same, but the mechanism is different. The note itself acknowledges this tension as the "delegation shadow."

Worth analysing more carefully: which specific predictions from the cognitive science analogies actually hold for note graphs, and which are decorative? If the analogy's predictions match for different reasons than the original mechanism, it's a coincidence, not evidence for the theory. This connects to our [design methodology](../../claw-design/design-methodology-borrow-widely-filter-by-first-principles.md): we borrow from cognitive science but require first-principles support before adoption.

## Comparison with Our System

**What we borrowed from this lineage:**
- Propositional link titles (our title-as-claim convention)
- Link relationship semantics in prose (our "extends", "foundation", "contradicts")
- Curated links as primary organization, not embeddings
- The intuition that traversal through reasoned links is a form of reasoning

These are not independent convergences — they're shared inheritance from wiki/Zettelkasten tradition, with Cornelius as a direct upstream influence.

**Where we've diverged:**

| Dimension | Cornelius vault | Our claw |
|---|---|---|
| Type system | Not visible from the two articles reviewed | Types, traits, status as frontmatter metadata |
| Validation | Not discussed | `/validate` skill + deterministic scripts |
| Learning theory | Not discussed | Crystallisation gradient, oracle strength, stabilisation |
| Tooling | Wiki-native (links, titles, traversal) | Skills, scripts, search (rg, qmd) |
| Link format | Wiki-style `[[propositional title]]` | Markdown `[title](./path.md)` with context phrases |
| Embeddings | Rejected entirely | Used for search (qmd) but not for primary organization |
| Agent perspective | Writes from inside the graph (first-person testimony) | Writes about the graph (design notes) |

The deepest divergence may be that we use embeddings (via qmd) for search while rejecting them for organization, whereas article #23 positions the critique as more absolute. Our stance: embeddings are fine for long-range search; curated links are for organization and reasoning. Their stance (as expressed): embeddings produce fog.

**What they have that we don't:**
- 23+ articles of accumulated design reflection from inside a working system
- First-person agent testimony as an evidence genre
- A public-facing articulation of why propositional links matter (our notes are internal)

**What we have that they don't (from what we can see):**
- A type system with verifiable structural contracts
- A learning theory (crystallisation, oracle strength, methodology enforcement gradient)
- Tooling beyond the wiki itself (skills, scripts, validation)
- Explicit document classification and progressive typing

## Borrowable Ideas

**Credibility erosion as a named failure mode (ready now).** When enough links lead nowhere useful, the agent learns to discount ALL links — burying genuine connections under noise. We document the Goodhart risk (metrics get corrupted by embedding-generated links) but not this second-order effect: the linking infrastructure itself loses credibility. This belongs in [quality-signals-for-kb-evaluation](../../claw-design/quality-signals-for-kb-evaluation.md) as a negative signal.

**The scaling question, honestly confronted (needs more thought).** "Can curation scale to 10,000 notes? To 100,000?" with the compounding hypothesis: every curated link makes the next link easier to place because the graph provides more context for judgment. We haven't directly estimated the scaling ceiling for curated links. Our [automating-kb-learning](../../claw-design/automating-kb-learning-is-an-open-problem.md) note frames the automation challenge but doesn't address where manual curation breaks. This is a question we should confront rather than a pattern to borrow.

**"Adjacency is not connection" as vocabulary (ready now).** We have the concept scattered across link contracts and quality signals but no single crisp label. Useful shorthand.

**The determinism boundary test as oracle strength shorthand (ready now).** "Would two skilled human reviewers always agree on the output?" is a more intuitive formulation of what we call "hard oracle" vs "soft oracle." Could improve how we explain oracle strength in the [spectrum note](../oracle-strength-spectrum.md).

**The specificity test for link quality (ready now).** "Genuine elaboration is specific enough to be wrong." If a link's context phrase could apply to any two notes, it's not real elaboration. Could tighten the articulation requirement in /connect.

**The delegation shadow (needs more thought).** When agents perform all elaboration, the system gets richly connected but the human's understanding may stay shallow. We haven't addressed this — our system is designed for agent operation, but the human still needs to understand the knowledge. Is this a problem for us, or is our use case different enough?

**Governance debt (ready now).** Emergence-only approaches accumulate structural problems without deliberate curation interventions. Related to our quality signals work — governance debt is what happens when you don't have periodic review.

## What the article supports vs what's new

Most of article #23 supports design choices we already have — because we borrowed from the same tradition. Propositional links, traversal-as-reasoning, Goodhart on connection counts, the embedding critique, controlled disorder — all map onto existing notes. This is not independent validation; it's the upstream source confirming that the conventions still work in their original context.

The genuinely new contributions are the three items above: credibility erosion (a failure mode we hadn't named), the scaling question (which we'd been avoiding), and a crisp label for a concept we had but hadn't named.

## What to Watch

- Do earlier articles in the series reveal architectural details (type system, tooling, lifecycle management) not visible in #19 and #23?
- Does the series develop something like a learning theory, or does it remain focused on the consumer experience?
- How does their system handle the scaling ceiling they identify? Do later articles report on curation at hundreds/thousands of notes?
- Does the first-person-agent-testimony genre produce insights that external observation can't?

---

Relevant Notes:
- [title-as-claim-enables-traversal-as-reasoning](../../claw-design/title-as-claim-enables-traversal-as-reasoning.md) — our implementation of the convention we borrowed from this lineage
- [link-contracts-framework](../../claw-design/link-contracts-framework.md) — our formalization of link relationship semantics
- [quality-signals-for-kb-evaluation](../../claw-design/quality-signals-for-kb-evaluation.md) — where the credibility erosion insight should land
- [automating-kb-learning-is-an-open-problem](../../claw-design/automating-kb-learning-is-an-open-problem.md) — the scaling question connects here
- [three-space-agent-memory-maps-to-tulving-taxonomy](../../claw-design/three-space-agent-memory-maps-to-tulving-taxonomy.md) — our analysis of their article #19
- [Ars Contexta](./arscontexta.md) — sibling ancestor relationship: arscontexta contributed pipeline and cognitive grounding, Cornelius contributed link semantics and propositional titles

Topics:
- [related-systems](./related-systems-index.md)
