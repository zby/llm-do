---
description: Entry point to the llm-do knowledge system — start here to navigate
type: moc
---

# index

Welcome to the llm-do knowledge system. This index connects design notes, architecture decisions, and active work threads.

## Agent Memory

- [identity](../../arscontexta/self/identity.md) — who the agent is and how it approaches this project
- [methodology](../../arscontexta/self/methodology.md) — how the agent processes and connects knowledge
- [goals](../../arscontexta/self/goals.md) — current active threads and focus areas

## Area Indexes

- [pydanticai-upstream-index](./pydanticai-upstream-index.md) — proposed PydanticAI changes, upstream issues, and how they affect llm-do (toolset lifecycle, approval wrapping, Traits API)

## Notes

- [dynamic-agents-runtime-design](./dynamic-agents-runtime-design.md) — design for runtime creation and invocation of agents (`agent_create`/`agent_call`), including session registry, PydanticAI tool lifecycle constraints, and approval interaction
- [pure-dynamic-tools](./pure-dynamic-tools.md) — LLM-authored tools that can only call agents, enabling safe dynamic orchestration via RestrictedPython sandbox
- [subagent-onboarding-protocol](./subagent-onboarding-protocol.md) — bidirectional setup conversation before subagent execution, addressing single-shot invocation limitations

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
