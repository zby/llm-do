---
description: Crystallisation systematises the out-of-band optimisations every deployed system accumulates — achieving continuous learning through versioned artifacts, whether human-driven or automated
areas: [index]
---

# Crystallisation Is Continuous Learning

## The Claim

AI labs frame "continuous learning" as a weight-update problem: how do you adapt a deployed model to new data, new tasks, and shifting distributions without a full retraining cycle? The standard approaches — fine-tuning on deployment logs, online learning, experience replay — all modify the model's parameters.

But the goals these approaches pursue — durable adaptation during deployment, accumulation of task-specific knowledge, improved performance over time — are exactly what [crystallisation](crystallisation-learning-timescales.md) already achieves. Not through weights, but through repo artifacts: prompts, schemas, evals, tools, and deterministic code that accumulate in version control.

This is not a metaphorical equivalence. A system that progressively extracts patterns from LLM behavior into testable, diffable, reviewable artifacts is doing genuine system-level learning. The system's behavior improves over time; the improvement persists across sessions; and the mechanism is more transparent than anything weight-based approaches can offer.

## Why Artifacts Beat Weights

Weight-based continuous learning inherits deep problems:

| Property | Weight updates | Repo artifacts |
|----------|---------------|----------------|
| **Inspectability** | Opaque — no one can read what was learned | Diffable — every change is a readable commit |
| **Catastrophic forgetting** | Major unsolved problem — new learning degrades old capabilities | Non-issue — adding a new tool doesn't break existing ones |
| **Rollback** | Expensive and lossy — requires checkpointing infrastructure | Trivial — `git revert` |
| **Verification** | Statistical at best — measure overall benchmark scores | Precise — individual evals, unit tests, CI gates |
| **Deployment** | Requires serving infrastructure changes | Standard deployment — prompts and code ship like any other artifact |
| **Composability** | Monolithic — all knowledge is entangled in a single weight matrix | Modular — each artifact is independent and can be tested in isolation |

The Karpathy verifiability framing sharpens this: a task is verifiable to the extent it is **resettable** (you can retry), **efficient** (retries are cheap), and **rewardable** (you can evaluate automatically). Repo artifacts score higher on all three dimensions than weight updates. You can re-run a prompt test in seconds. You can evaluate the output against assertions. You can iterate dozens of times before committing. Weight updates require training runs, validation sets, and careful monitoring for regression.

## Comparison with Alternatives

### Fine-tuning

Fine-tuning is the most direct form of weight-based continuous learning: take deployment data, update the model. It works, but it's expensive (compute), risky (forgetting), opaque (what did the model learn?), and coarse (the whole model changes when you wanted to improve one behavior).

Crystallisation achieves the same narrowing of the behavior distribution, but through external artifacts. Instead of fine-tuning a model to format dates consistently, you extract a deterministic `format_date()` function. Instead of fine-tuning for a house style, you version the system prompt with examples. The effect on system behavior is equivalent; the mechanism is inspectable.

### RAG

Traditional RAG — a single retrieve-then-answer step — is largely obsolete. What people actually build now is agentic RAG: retrieval happens inside an agentic loop, where the agent decides what to search for, evaluates what it finds, and searches again if needed. This is a much stronger pattern.

Agentic RAG fits naturally inside the crystallisation framework. The repo itself is the knowledge base: documents, schemas, examples, prior decisions — all versioned, all improving over time. The agent searches them as part of its work loop, and the artifacts it retrieves are the same ones that crystallisation continuously refines. The difference from a traditional vector store is that these artifacts are structured, testable, and subject to the same versioning and review as code. You don't just retrieve knowledge — you retrieve knowledge that has been progressively verified and hardened.

The old critique of RAG — fragile retrieval, unstructured knowledge, no way to test or diff what's stored — applies to the one-shot vector-store pattern. Agentic retrieval over a crystallised repo sidesteps all three: the agent compensates for retrieval imprecision by iterating, the knowledge is structured by design, and every artifact is diffable and reviewable.

### Automated Prompt Optimization

Systems like DSPy and ProTeGi search over prompt components to optimize against an objective. This is not merely crystallisation-adjacent — it's an automated instance of the same loop. The artifacts are prompts, the optimization is iterative, the improvement persists. What these systems lack is the broader framework: the verifiability gradient, the progression from optimized prompts to schemas to deterministic code, and the infrastructure for versioning, testing, and reviewing what was learned.

Crystallisation provides that system. DSPy discovers better prompts; crystallisation provides the framework to harden those discoveries into progressively more verifiable forms, track them in version control, and test them in CI. The [adaptation taxonomy for agentic AI](research/adaptation-agentic-ai-analysis.md) identifies concrete data-driven triggers for when to crystallise (e.g., "tool consistently fails with certain input patterns") versus when to soften back to prompts, providing the feedback signals that drive this learning loop. The combination is the full picture: automated search for what works, systematic infrastructure for preserving and verifying what was found.

## The Verifiability Gradient as Learning Gradient

Each grade of crystallisation — from restructured prompts through schemas and evals to deterministic code — represents a different level of "learning" by the deployed system. Moving down the [verifiability gradient](crystallisation-learning-timescales.md) is learning: the substrate is different from neural weight updates, but the function — adapting system behavior to deployment experience — is identical. At the very top of this gradient sit [dynamic agents](dynamic-agents-runtime-design.md) — ephemeral, experimental workers created at runtime where patterns have not yet stabilised enough for repo artifacts. They represent the pre-crystallisation state: the exploration phase before the learning loop has enough signal to extract durable knowledge.

## Why This Framing Matters

Calling crystallisation "continuous learning" is not just terminological. It reframes what deployed AI systems need:

1. **Infrastructure investment shifts.** Instead of building online learning pipelines, invest in eval frameworks, prompt versioning, and CI for AI artifacts. These are mature, well-understood tools.

2. **Systematised out-of-band optimisation.** Every deployed LLM system accumulates informal tweaks — prompt adjustments, output post-processing, workflow changes — that improve behavior but live outside the model. These are learning, but ad-hoc learning: undocumented, untested, unreproducible. Crystallisation systematises this. The loop can be human-driven (reviewing diffs, approving changes, catching bad assumptions) or automated (search over prompt components, eval-driven iteration) — the point is that optimizations land as versioned, testable artifacts rather than scattered tribal knowledge. Research on [professional developers using AI agents](related_works/professional-developers-ai-agents.md) confirms the human-driven variant empirically: experienced developers naturally practice this loop. But the framework accommodates both modes — and the automated mode is where it connects to DSPy and similar systems.

3. **Verifiability as the metric.** Instead of asking "how do we keep the model learning?", ask "how verifiable is each piece of our system?" and push toward more verifiable forms. The [theory document](../theory.md) describes this as the stabilise/soften cycle: crystallise patterns when they emerge, soften back when new requirements appear. The [python-agent-annotation-brainstorm](python-agent-annotation-brainstorm.md) explores the practical mechanisms for this bidirectionality — decorators and annotations that make it easy to move between LLM-based workers and deterministic Python code, lowering the friction of moving along the crystallisation gradient.

---

Relevant Notes:
- [crystallisation-learning-timescales](crystallisation-learning-timescales.md) — foundation: defines the three timescales and the verifiability gradient this note builds on
- [dynamic-agents-runtime-design](dynamic-agents-runtime-design.md) — exemplifies the pre-crystallisation state: ephemeral agents sit at the top of the verifiability gradient where patterns are too unstable for durable artifacts
- [adaptation-agentic-ai-analysis](research/adaptation-agentic-ai-analysis.md) — extends: provides data-driven triggers (error patterns, repeated tool failures) for when to crystallise vs soften, grounding the learning loop in concrete signals
- [professional-developers-ai-agents](related_works/professional-developers-ai-agents.md) — empirical evidence that professional developers naturally practice the crystallisation loop: validate, extract patterns, stabilise
- [python-agent-annotation-brainstorm](python-agent-annotation-brainstorm.md) — enables: the softening/stabilising paths lower friction for moving along the crystallisation gradient between LLM workers and deterministic code

Topics:
- [index](index.md)
