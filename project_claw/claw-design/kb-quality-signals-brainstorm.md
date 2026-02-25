# Quality signals for KB evaluation

Brainstorming: what signals — structural, semantic, or hybrid — could serve as soft oracles for KB quality? No single signal is reliable, but many weak signals combined might provide enough guidance to drive a learning loop without waiting for usage data.

The analogy: AlphaGo works because the game has a perfect verifier. KBs don't. But we don't need a perfect verifier to learn — we need a signal that's better than random. Can we manufacture one from a basket of imperfect signals?

## Static signals (measurable at any point)

**Graph topology:**
- Orphan rate — notes with no inbound links. High orphan rate suggests notes are created faster than connected. Easy to measure, clearly actionable.
- Hub-and-spoke vs mesh — are notes connected to each other, or only through indexes? A mesh suggests genuine integration; hub-and-spoke suggests cataloguing without understanding.
- Cluster coefficient — how tightly connected are local neighborhoods? High coefficient within an area suggests coherent concepts; low coefficient suggests the area groups unrelated notes.
- Bridge nodes (betweenness centrality) — notes connecting otherwise separate clusters. These are likely valuable syntheses. If bridge count drops, clusters are becoming siloed.
- PageRank / eigenvector centrality — identifies structurally important nodes. Useful not as a quality signal directly, but as a way to prioritise: high-centrality notes with problems (poor description, stale content) are higher-priority fixes.
- Link reciprocity — if A links to B, does B link back or to related concepts? Low reciprocity might indicate one-directional references that should be bidirectional.

**Content quality proxies:**
- Description uniqueness — pairwise similarity of descriptions. High similarity between two notes suggests either redundancy or poor discrimination. Both are actionable.
- Description length distribution — too short (< 50 chars) → likely uninformative. Too long (> 200 chars) → summary not filter. The distribution shape tells you about overall discipline.
- Title-as-claim ratio — what fraction of note titles read as claims vs topics? Can be approximated: titles starting with verbs or containing "is/are/should/enables" are likely claims.
- Frontmatter completeness — what % have description, type, areas? Declining completeness over time suggests declining discipline.

**Structural health:**
- Dangling link rate — links pointing to non-existent files. Purely deterministic, always bad.
- Index coverage — what % of notes appear in at least one area index? (Directory indexes don't count — they're auto-generated.)
- Index staleness — do all index entries point to existing files? Do indexes mention notes that have been renamed or deleted?
- Note age vs connection count — old notes with few connections may be stale or orphaned by topic drift.

## Metamorphic relations (testable over mutations)

Instead of testing "is this KB good?", test "did this change make it better or worse?"

- **Split invariant:** splitting a note into two should preserve or increase total inbound links. If links decrease, the split broke something.
- **Synthesis test:** a synthesis note should link to at least 2 source notes. If it doesn't, it's not actually synthesising.
- **Connection test:** adding a note to an area should connect to at least one other note in that area (beyond the index). If it doesn't, does it belong there?
- **Rename consistency:** renaming a note should update all backlinks. Deterministic, automatable.
- **Deletion impact:** removing a note should not create orphans among notes that only linked to it. If it does, those notes need reconnection.
- **Link articulation:** every new link should pass the "because" test — can the relationship be articulated? This is a soft check (LLM judgment), but it's a metamorphic relation: "link exists" should imply "relationship is articulable."

## Compound signals (combining weak signals)

Individual signals are noisy. Combinations might be more informative:

- High PageRank + no description → high-value node with poor discoverability. Priority fix.
- Many outbound links + no inbound → possibly a hub that's not itself indexed. Or a note that references others without contributing its own claim.
- High cluster coefficient within area + no bridges to other areas → silo. The area's concepts don't connect to the broader KB.
- Rising orphan rate + stable note count → connections are decaying faster than notes are created. Maintenance problem.
- Low description uniqueness within an area → the area's notes aren't well-differentiated. Split or merge candidates.

## The "many weak signals" hypothesis

No single signal above is a reliable quality indicator. But a composite score — weighting multiple signals — might be. This is the same move as ensemble methods in ML: individual weak learners combined into a strong one.

The question is whether the signals are independent enough. If they all correlate (e.g. well-connected notes also have good descriptions because the same discipline produces both), the ensemble doesn't add much. If they capture different failure modes (orphans vs poor descriptions vs siloed clusters), the ensemble is genuinely stronger.

Testable by: run all signals on the current KB, identify the notes each signal flags, and check overlap. If different signals flag different notes, the ensemble has value.

## What could drive a learning loop

If the composite signal is good enough, the boiling cauldron (from kb-learning-loop) could work:
1. Propose a mutation (extract, split, synthesise, relink, regroup)
2. Measure composite quality score before and after
3. Accept mutations that improve the score, reject those that don't
4. Over time, learn which mutation types improve which signals

This doesn't require usage data — it runs on structure alone. Usage data (query logs, retrieval failures) would make it better, but structural signals might be enough to start.

## Neighborhood evaluation (LLM + structure hybrid)

A technique already in use: load a note together with all its linked pages (outbound and inbound), then ask the LLM to evaluate the ensemble. This regularly surfaces actionable edits — missing connections, inconsistencies between neighbors, redundancy, conclusions implied by linked notes but not drawn.

This is qualitatively different from the structural signals above. The graph structure determines *what context to load* (the note's neighborhood); the LLM does the *judgment* that structural signals can't. The evaluation is local — you don't need the entire KB, just the 1-hop neighborhood — which keeps context manageable.

What this catches that structural signals miss:
- A note contradicts a neighbor (content-level, not structural)
- Two linked notes together imply something neither says — a synthesis opportunity
- A note repeats what a neighbor already covers — redundancy invisible to link counts
- A link exists but the relationship isn't articulated in either note's prose
- A neighbor mentions a concept that should be linked but isn't

What structural signals catch that this misses:
- Global topology problems (siloed clusters, orphans outside the neighborhood)
- Trends over time (rising orphan rate, declining description quality)
- Cross-area issues (the same concept under different names in different areas)

The two approaches are complementary: structural signals tell you *where* to look (which notes or areas are structurally unhealthy), neighborhood evaluation tells you *what's wrong* and suggests fixes. A learning loop could use structural signals to prioritise which neighborhoods to evaluate, then use LLM judgment within those neighborhoods to propose mutations.

This also connects to the metamorphic approach: you could evaluate a neighborhood before and after a mutation, using LLM judgment to assess whether coherence improved. That's a soft oracle over mutations — not structural, but not purely vibes either.

## LLM critique of individual notes

An obvious signal: ask the LLM to critique a note. The problem is calibration — LLMs tend to always find fault, so you can't use "number of faults" as a quality score. The critique is biased toward reporting problems regardless of actual quality.

Possible calibration strategies:
- **Relative comparison** — compare two notes ("which is better structured?") or two versions of the same note, rather than "is this good?" Pairwise ranking sidesteps the absolute bias.
- **Cross-note baseline** — run the same critique prompt on all notes. If 90% are flagged for "could be more concise," that's the LLM's prior, not a signal. If 10% are flagged for "contradicts its own description," those 10% probably do. The fault's frequency across the corpus is more informative than any individual critique.
- **Fix-and-re-critique** — apply the suggested fix, critique again. If the LLM finds new faults of equal severity, the critique is noise (it will always find something). If faults genuinely resolve and aren't replaced, it was signal.
- **Structured rubrics** — constrain what the LLM can critique (description discriminates? title reads as claim? links articulated?) rather than open-ended "find problems." Rubric items can be individually validated against the cross-note baseline.

The fix-and-re-critique approach is itself metamorphic: you're not testing absolute quality, you're testing whether a transformation (the fix) changes the output of the evaluation. If the evaluation is stable under the fix, the original critique was noise.

## Open questions

- Which signals are cheapest to compute? Start with those.
- Which signals are most correlated? Drop redundant ones.
- Can we validate any of this on the current KB? Run the signals, see what they flag, check if the flagged notes are genuinely low-quality.
- How do we weight the signals? Start with equal weights and learn?
- Is there a risk of Goodhart's law — optimising structural signals at the expense of actual quality? (A note linking to everything would score well on connectivity but poorly on precision.)
- The Goodhart risk suggests we need both positive signals (connectivity, coverage) and negative signals (vagueness detectors, redundancy checks) — the negative signals constrain the positive ones.
