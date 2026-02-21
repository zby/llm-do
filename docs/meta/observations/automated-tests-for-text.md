# Automated tests for text

Text artifacts can be tested like software if you define contracts per document type. The same test pyramid applies: cheap deterministic checks at the base, LLM-based rubric grading in the middle, cross-document corpus checks at the top.

We have note types now (analysis, design, review, etc.). Each type could have its own contracts — an analysis needs different things than an insight or a spec.

Key principle: build contracts from real failures, not from a taxonomy of possible checks. Same way you build a test suite — add a test when something breaks, not before.

Levels we might use:
- **Deterministic** — required sections, description present, link validity, no dangling wiki-links, length
- **LLM rubric** — clarity, single clear thesis, claims sourced or marked as assumptions
- **Corpus compatibility** — contradiction check against existing notes, terminology alignment, duplicate detection

A knowledge base is a collection of stored LLM outputs — each note is a stabilized sample from a distribution. So note testing is an application of the broader [artifact testing problem](../../notes/storing-llm-outputs-is-stabilization.md). The distinction between testing the prompt (will it produce good notes?) and testing the artifact (is *this* note good?) matters here: the pyramid above is all artifact testing.

We haven't built any of this yet. Start when we hit a concrete quality problem that a check would have caught.
