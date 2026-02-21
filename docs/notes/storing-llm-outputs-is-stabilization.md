---
description: Choosing to keep a specific LLM output collapses a distribution to a point — the same stabilizing move the theory doc describes for code, applied to artifacts
type: design
areas: [index]
status: speculative
---

# Storing LLM outputs is stabilization

A prompt admits a distribution of outputs. Each run samples from that distribution — rerunning might give something better or worse. When you choose to keep a specific output, you're collapsing that distribution to a point. This is the same stabilizing move described in [theory.md](../theory.md) for code, but applied to the artifact rather than the implementation.

The theory doc already says "version both spec and artifact" because "regeneration is a new projection from the same spec — a different sample, not a deterministic rebuild." The insight here is *why* that matters: storing an artifact is itself a stabilization decision. You're not just saving a file — you're committing to one sample from a space of possibilities.

This applies broadly:
- **Generated code** — the prompt could produce many valid implementations; you lock down the one that works
- **Generated documents** — a note-writing prompt produces varying quality; you keep the good one
- **Configuration** — an LLM suggests settings; you freeze the ones that behave well

In each case, the stored artifact is more stable than the process that created it. The prompt remains stochastic; the artifact is now deterministic.

## Testing implications

This creates two distinct testing targets:

1. **Testing the distribution** (prompt testing) — does this prompt reliably produce good outputs? Run N times, check statistical properties. You're testing the generator.
2. **Testing the sample** (artifact testing) — is this specific output good? Check structural properties, quality criteria, corpus consistency. You're testing the product.

You need both because even a well-tuned prompt produces variable output — you can't skip artifact testing. And artifact testing alone doesn't tell you whether the prompt will work next time.

The theory doc covers distribution testing (line 196: "statistical hypothesis testing, not assertion equality") but doesn't address sample testing. Artifact testing is closer to static analysis or linting — checking properties of a thing that already exists, not verifying behavior of a process.

## Generator/verifier: an alternative to constraining prompts

There are two strategies for getting reliable output from a stochastic generator:

1. **Constrain the generator** — tighter prompts, more examples, lower temperature. Reduces variance, but caps the upside. You get consistently mediocre results.
2. **Filter the samples** — high-variance generator + quality gate. Keeps the upside, rejects the failures. A prompt that sometimes produces great output and sometimes garbage can outperform a "safe" prompt that always produces mediocre output — if you have a good filter.

This is the generator/verifier pattern: verification is often cheaper than generation. For code, you can run tests. For text, you need the automated checks described in the testing pyramid (deterministic → LLM rubric → corpus).

Strategy 2 is only viable when verification is cheap relative to generation. It also reframes the relationship between prompt testing and artifact testing: they're not just separate concerns, they're *complementary strategies*. Prompt testing tells you the distribution is worth sampling from. Artifact testing is the filter that makes a high-variance distribution usable.

The implication for stabilization: a good filter lets you *not* stabilize the prompt. You keep the stochastic generator because the verifier handles quality. Constraining the prompt is pushing reliability into the generator instead — a different tradeoff, not a strictly better one.

---

Relevant Notes:
- [crystallisation-learning-timescales](./crystallisation-learning-timescales.md) — extends the stabilization gradient with a new application: output artifacts, not just code

Topics:
- [index](./index.md)
