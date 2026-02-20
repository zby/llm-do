---
description: Entry point to the llm-do knowledge system — start here to navigate
type: moc
---

# index

llm-do is built on the observation that deployed AI systems adapt at three timescales — training, in-context, and crystallisation — and that the third is systematically undervalued. The [verifiability gradient](./crystallisation-learning-timescales.md) from prompt tweaks to deterministic code is the organising principle: every design decision in llm-do is about making it easier to move along this gradient.

## Core Concept

- [crystallisation-learning-timescales](./crystallisation-learning-timescales.md) — the foundational claim: three timescales, the verifiability gradient, and why repo artifacts beat weights

## Notes

- [crystallisation-is-continuous-learning](./crystallisation-is-continuous-learning.md) — argues this achieves what labs pursue as "continuous learning" via weight updates
- [inspectable-substrate-not-supervision-defeats-the-blackbox-problem](./inspectable-substrate-not-supervision-defeats-the-blackbox-problem.md) — counters Chollet's "agentic coding produces blackbox models" — the substrate (repo artifacts vs weights) determines verifiability, not who inspects
- [dynamic-agents-runtime-design](./dynamic-agents-runtime-design.md) — the top of the gradient: ephemeral agents for patterns not yet stable enough to crystallise
- [pure-dynamic-tools](./pure-dynamic-tools.md) — LLM-authored tools that can only call agents, enabling safe dynamic orchestration via RestrictedPython sandbox
- [subagent-onboarding-protocol](./subagent-onboarding-protocol.md) — bidirectional setup conversation before subagent execution, addressing single-shot invocation limitations

## Area Indexes

- [approvals-index](./approvals-index.md) — threat model, capability taxonomy, UI integration, and upstream simplification
- [pydanticai-upstream-index](./pydanticai-upstream-index.md) — proposed PydanticAI changes, upstream issues, and how they affect llm-do (toolset lifecycle, approval wrapping, Traits API)

## Agent Memory

- [identity](../../arscontexta/self/identity.md) — who the agent is and how it approaches this project
- [methodology](../../arscontexta/self/methodology.md) — how the agent processes and connects knowledge
- [goals](../../arscontexta/self/goals.md) — current active threads and focus areas

## Decisions (ADRs)

- [001-thin-custom-prefix-adapter-and-oauth-gating](../adr/001-thin-custom-prefix-adapter-and-oauth-gating.md)
- [002-agent-args-as-public-input-contract](../adr/002-agent-args-as-public-input-contract.md)
- [003-opt-in-tool-model](../adr/003-opt-in-tool-model.md)
- [004-unified-tool-plane](../adr/004-unified-tool-plane.md)
- [005-runner-harness-vs-clai](../adr/005-runner-harness-vs-clai.md)
- [006-runtime-core-vs-simpler-runtime](../adr/006-runtime-core-vs-simpler-runtime.md)

## Getting Started

1. Read self/identity.md to understand the agent's role
2. Browse docs/notes/ for existing design explorations
3. Use /arscontexta:extract to process a source into connected notes
4. Use /arscontexta:connect to find relationships between notes
