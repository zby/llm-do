---
description: Every act of stabilisation — reducing variance, increasing determinism — is learning in Simon's sense. It trades generality for compound gains in reliability, speed, and cost. Crystallisation is the most dramatic form; softening is learning on the other axis.
type: structured-claim
traits: []
areas: []
status: current
---

# Stabilisation is learning

Herbert Simon: learning is [any change that produces a more or less permanent change in a system's capacity](learning-is-capacity-change.md) for adapting to its environment. Every stabilisation fits this definition. When you reduce variance — store an LLM output, write a convention, extract a deterministic function — you increase the system's adaptive capacity for the specific case stabilised, trading generality for [compound gains in reliability, speed, and cost](learning-is-capacity-change.md).

## Evidence

### The spectrum of stabilisation

Stabilisation isn't just crystallisation (prompt → schema → code). It starts earlier and includes smaller acts:

| Stabilisation | What changes | Capacity gain |
|--------------|-------------|---------------|
| [Store an LLM output](storing-llm-outputs-is-stabilization.md) | Collapse a distribution to a point | One decision becomes permanent |
| Write a description field | Enable search without reading | One note becomes findable |
| Create a convention | Make future operations predictable | All operations of that kind become faster |
| Add structured sections | Enable type-specific operations | The document affords new workflows |
| Extract a deterministic function | Move from LLM to code | One operation becomes reliable, fast, free |

Each step trades generality (the document/process could have been anything) for something more specific and reliable. The mechanism is the same across the whole spectrum — it's just that full crystallisation changes the substrate entirely, making the compound gain largest.

### Softening is also learning

The reverse — softening, replacing a stabilised component with a general-purpose one — is also learning. It increases generality at the cost of the compound. When scale makes a general approach good enough on reliability+speed+cost, the [bitter lesson boundary](bitter-lesson-boundary.md) tells you to soften. Both directions are capacity change; they just operate on different [dimensions of capacity](learning-is-capacity-change.md).

### The KB as evidence

The KB itself demonstrates this. Every session that improves notes, sharpens connections, or discovers principles is stabilisation — and therefore learning. From fixing a typo (narrow scope) to discovering design principles (wide scope), the mechanism is the same: reduce variance, increase capacity. This is why [the KB already has a learning loop](../claw-design/automating-kb-learning-is-an-open-problem.md) — the open problem is automating the judgment-heavy stabilisations.

## Reasoning

### The stabilise/soften cycle is a learning cycle

The stabilise/soften cycle described in the [theory document](../../docs/theory.md) is, viewed through Simon's definition, a learning cycle. Each stabilisation step makes the system more capable for the specific case it handles. Each softening step makes it more capable for the general case. The cycle isn't maintenance — it's how the system learns.

The [verifiability gradient](crystallisation-learning-timescales.md) — from restructured prompts through schemas and evals to deterministic code — is a compound capacity gradient: reliability, speed, and cost all improve together as you move down it. At the top sit [dynamic agents](dynamic-agents-runtime-design.md) — maximum generality, minimum reliability. At the bottom sits deterministic code — minimum generality, maximum reliability. The system's learning trajectory is its movement along this gradient.

### Continuous learning is stabilisation during deployment

AI labs frame "continuous learning" as adapting a deployed model to new data without retraining — the hot topic in production AI. The claim here is that stabilisation through versioned artifacts [achieves the same goals](./continuous-learning-is-stabilisation-during-deployment.md) — durable adaptation, task-specific knowledge accumulation, improved performance over time — and does it better on inspectability, rollback, verification, and composability. The continuous learning problem is a special case: stabilisation that happens during deployment, on the basis of deployment experience.

## Caveats

- **Not all learning is stabilisation.** Weight-based learning captures distributional knowledge (style, tone, world knowledge) that doesn't reduce to explicit artifacts. The claim is that stabilisation covers most of what deployed systems need for continuous improvement, not everything.
- **Stabilisation requires curation.** Artifacts go stale, schemas need updating, conventions drift. The process assumes an active curation loop, whether human-driven or automated.
- **The compound gain only fully applies to operations that completely crystallise.** Partially stabilised operations — where a script handles 80% of cases and an LLM handles the rest — get partial gains, and the boundary needs ongoing maintenance.

---

Relevant Notes:
- [learning-is-capacity-change](learning-is-capacity-change.md) — foundation: provides the capacity decomposition (generality vs reliability+speed+cost) that makes this claim precise
- [continuous-learning-is-stabilisation-during-deployment](./continuous-learning-is-stabilisation-during-deployment.md) — extends: the specific argument that AI labs' continuous learning is achievable through artifact-based stabilisation, with detailed comparisons to fine-tuning, RAG, and automated prompt optimization
- [crystallisation-learning-timescales](crystallisation-learning-timescales.md) — foundation: defines the three timescales and the verifiability gradient
- [bitter-lesson-boundary](bitter-lesson-boundary.md) — connects: the calculator/vision-feature boundary determines when stabilisation is permanent vs when softening is needed
- [storing-llm-outputs-is-stabilization](storing-llm-outputs-is-stabilization.md) — instance: the simplest form of stabilisation-as-learning
- [automating-kb-learning-is-an-open-problem](../claw-design/automating-kb-learning-is-an-open-problem.md) — applies: the KB's manual learning loop is stabilisation; automating the judgment-heavy parts is the open problem
- [dynamic-agents-runtime-design](dynamic-agents-runtime-design.md) — exemplifies the pre-stabilisation state: ephemeral agents at the top of the verifiability gradient
- [oracle-strength-spectrum](oracle-strength-spectrum.md) — the Karpathy verifiability properties (resettable, efficient, rewardable) map to oracle strength; determines when stabilisation is possible
- [methodology-enforcement-is-stabilisation](../claw-design/methodology-enforcement-is-stabilisation.md) — applies: the instruction → skill → hook → script gradient is stabilisation applied to methodology

Topics:
