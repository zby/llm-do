---
description: Three timescales of AI learning — training, in-context, and crystallisation
---

# Crystallisation: The Missing Middle

## Three Timescales

AI systems learn at three timescales, each with a different substrate:

| Timescale | When | Substrate | Properties |
|-----------|------|-----------|------------|
| **Training** | Before deployment | Weights | Durable but opaque; requires a training pipeline; cannot incorporate deployment-specific information |
| **In-context** | Within a session | Context window | Inspectable but ephemeral; evaporates when the session ends |
| **Crystallisation** | Across sessions, during deployment | Repo artifacts | Durable, inspectable, and verifiable; accumulates over time |

Crystallisation is a third, distinct mode: learning that happens during deployment, like in-context learning, but persists durably, like training. What makes it possible is encoding knowledge into repo artifacts rather than weights or context.

## Why Repo Artifacts

Other things try to fill this space: RAG databases, memory files, fine-tuning on deployment logs. What distinguishes crystallisation is that the substrate is **repo artifacts** — prompts, schemas, eval suites, deterministic modules, tests — not unstructured memory notes or embedding vectors.

Repo artifacts are verifiable to varying degrees. A memory note like "remember to validate emails" can drift or contradict itself silently. A structured output schema enforces shape. A test fails loudly. Deterministic code removes the LLM from the loop entirely. Every grade along the way is an improvement over ephemeral context.

## Grades of Crystallisation

Deterministic code is the strongest form, but crystallisation is a gradient. Each step reduces reliance on the LLM and increases verifiability:

| Grade | Example | Verification | LLM dependence |
|-------|---------|-------------|----------------|
| Restructured prompts | Breaking a monolithic prompt into sections, naming steps | Human review | High — still fully LLM-interpreted |
| Structured output schemas | JSON schemas constraining response format | Schema validation — automated | Medium — LLM generates, but output shape is enforced |
| Prompt tests / evals | Assertions over LLM output across test cases | Probabilistic — statistical pass rates | Medium — LLM still does the work, but regressions are caught |
| Deterministic modules | Code that replaces what was previously LLM work | Automated — pass/fail | None — LLM is removed from this step |

The common thread: all grades are durable, version-controlled, and subject to review. The difference is how sharp the correctness boundary is and how much still depends on the LLM at runtime.

Crystallisation depends on the quality of the in-context learning that precedes it. An agent that writes a bad test crystallises a bad assumption. The quality gate is typically human approval — crystallisation is a human-AI collaborative process, not a purely autonomous one.

## Relation to the Hybrid VM Theory

The [theory document](../theory.md) describes llm-do as a hybrid VM where components move between stochastic (LLM) and deterministic (code) execution via two operations: **stabilizing** (stochastic → deterministic) and **softening** (deterministic → stochastic).

Crystallisation is the learning process that drives stabilizing. The theory describes *what* moves across the distribution boundary; crystallisation describes *how* — through deployment experience encoded into progressively harder artifacts:

| Theory concept | Crystallisation grade |
|----------------|----------------------|
| Fully stochastic | In-context learning only — nothing persisted |
| Shaping the distribution (prompts, schemas) | Restructured prompts, structured output schemas |
| Progressive stabilizing | Prompt evals catching regressions |
| Full stabilizing | Deterministic modules replacing LLM steps |

Softening is the opposite movement: extending into territory where we don't yet have enough information to crystallise. You add an LLM call to handle new cases, observe its behavior across sessions, and crystallise the patterns that emerge.

The full cycle: **soften to explore, crystallise to consolidate.** A component might start as an LLM call (quick to add), crystallise to code as patterns emerge (reliable and testable), then soften again when new requirements outgrow the rigid implementation. The system breathes.

## In llm-do

This framing describes the design rationale behind llm-do's architecture:

- `.agent` specs are crystallised interaction patterns
- Deterministic tool modules are crystallised capabilities
- `project.json` manifests are crystallised orchestration knowledge
- Tests verify that crystallised assumptions still hold
