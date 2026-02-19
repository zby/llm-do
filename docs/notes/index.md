---
description: Entry point to the llm-do knowledge system — start here to navigate
type: moc
---

# index

Welcome to the llm-do knowledge system. This index connects design notes, architecture decisions, and active work threads.

## Agent Memory

- [[identity]] — who the agent is and how it approaches this project
- [[methodology]] — how the agent processes and connects knowledge
- [[goals]] — current active threads and focus areas

## Area Indexes

- [[pydanticai-upstream-index]] — proposed PydanticAI changes, upstream issues, and how they affect llm-do (toolset lifecycle, approval wrapping, Traits API)

## Notes

- [[dynamic-agents-runtime-design]] — design for runtime creation and invocation of agents (`agent_create`/`agent_call`), including session registry, PydanticAI tool lifecycle constraints, and approval interaction
- [[pure-dynamic-tools]] — LLM-authored tools that can only call agents, enabling safe dynamic orchestration via RestrictedPython sandbox
- [[subagent-onboarding-protocol]] — bidirectional setup conversation before subagent execution, addressing single-shot invocation limitations

## Decisions (ADRs)

- [[001-thin-custom-prefix-adapter-and-oauth-gating]]
- [[002-agent-args-as-public-input-contract]]
- [[003-opt-in-tool-model]]
- [[004-unified-tool-plane]]
- [[005-runner-harness-vs-clai]]
- [[006-runtime-core-vs-simpler-runtime]]

## Getting Started

1. Read self/identity.md to understand the agent's role
2. Browse docs/notes/ for existing design explorations
3. Use /arscontexta:extract to process a source into connected notes
4. Use /arscontexta:connect to find relationships between notes
