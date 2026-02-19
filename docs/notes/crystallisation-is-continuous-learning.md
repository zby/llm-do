---
description: What labs pursue as "continuous learning" via weight updates is already achievable through crystallisation of repo artifacts
areas: [index]
---

# Crystallisation Is Continuous Learning

## The Claim

AI labs frame "continuous learning" as a weight-update problem: how do you adapt a deployed model to new data, new tasks, and shifting distributions without a full retraining cycle? The standard approaches — fine-tuning on deployment logs, online learning, experience replay — all modify the model's parameters.

But the goals these approaches pursue — durable adaptation during deployment, accumulation of task-specific knowledge, improved performance over time — are exactly what [[crystallisation-learning-timescales|crystallisation]] already achieves. Not through weights, but through repo artifacts: prompts, schemas, evals, tools, and deterministic code that accumulate in version control.

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

Retrieval-augmented generation puts knowledge in a vector store instead of weights. This solves some problems (knowledge is updatable, no retraining needed) but introduces others: retrieval quality is fragile, context windows are limited, and the knowledge remains unstructured — you can't test it, diff it, or review it.

Crystallised artifacts occupy a stronger position: a structured schema or a deterministic tool doesn't depend on retrieval quality. It's always present, always applies, and its correctness can be verified. RAG is appropriate for large, loosely structured knowledge bases; crystallisation is appropriate for patterns that have stabilised enough to encode precisely.

### Automated Prompt Optimization

Systems like DSPy and ProTeGi search over prompt components to optimize against an objective. This is crystallisation-adjacent — the artifacts are prompts, the optimization is iterative, the improvement persists. The difference is automation: prompt optimization is search over a space, while crystallisation (as practiced today) typically involves human judgment about what to extract.

The approaches are complementary. Automated optimization can discover better prompts; crystallisation can then harden the resulting patterns into more verifiable forms — from optimized prompts to schemas to code.

## The Verifiability Gradient as Learning Gradient

Each grade of crystallisation (as described in [[crystallisation-learning-timescales]]) represents a different level of "learning" by the deployed system:

- **Restructured prompts** — the system learned what framing works best (weakly verifiable)
- **Structured schemas** — the system learned the shape of correct output (moderately verifiable)
- **Evals and prompt tests** — the system learned what good behavior looks like (well verifiable)
- **Deterministic code** — the system learned the exact algorithm (fully verifiable)

Moving down this gradient is learning. The substrate is different from neural weight updates, but the function — adapting system behavior to deployment experience — is identical.

## Why This Framing Matters

Calling crystallisation "continuous learning" is not just terminological. It reframes what deployed AI systems need:

1. **Infrastructure investment shifts.** Instead of building online learning pipelines, invest in eval frameworks, prompt versioning, and CI for AI artifacts. These are mature, well-understood tools.

2. **The human-in-the-loop is a feature.** Weight-based learning tries to remove humans from the adaptation loop. Crystallisation keeps them in — reviewing diffs, approving changes, catching bad assumptions. For production systems handling real stakes, this is a strength.

3. **Verifiability as the metric.** Instead of asking "how do we keep the model learning?", ask "how verifiable is each piece of our system?" and push toward more verifiable forms. The [theory document](../theory.md) describes this as the stabilise/soften cycle: crystallise patterns when they emerge, soften back when new requirements appear.

---

Relevant Notes:
- [[crystallisation-learning-timescales]] — foundation: defines the three timescales and the verifiability gradient this note builds on
- [[capability-based-approvals]] — the human review loop that makes crystallisation safe is an instance of capability-based approval design

Topics:
- [[index]]
