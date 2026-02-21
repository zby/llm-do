---
description: Index of notes about proposed PydanticAI changes, upstream issues, and how they affect llm-do
type: index
status: current
---

# PydanticAI upstream index

Notes about PydanticAI design gaps, proposed changes, and how upstream decisions affect llm-do's architecture. These notes serve dual duty: internal design analysis and material for upstream engagement.

## The core issue

- [toolset-state-prevents-treating-pydanticai-agents-as-global](./toolset-state-prevents-treating-pydanticai-agents-as-global.md) — the upstream issue ([#4347](https://github.com/pydantic/pydantic-ai/issues/4347)): toolset state forces per-call Agent construction despite agents being documented as global/stateless

## Toolset lifecycle

- [toolset-state-spectrum-from-stateless-to-transactional](./toolset-state-spectrum-from-stateless-to-transactional.md) — taxonomy of seven state patterns; most tools hide the lifecycle problem until sub-agents or parallelism surface it
- [proposed-toolset-lifecycle-resolution-for-pydanticai](./proposed-toolset-lifecycle-resolution-for-pydanticai.md) — three-layer proposal: document what exists, make factories first-class, add `for_sub_agent()` hooks
- [stateful-flag-evaluation-against-toolset-spectrum](./stateful-flag-evaluation-against-toolset-spectrum.md) — evaluates the proposed `stateful` flag against concrete examples for all seven categories; proposes tiered mechanisms for gaps including framework implications for llm-do

## Approval wrapping

- [we-want-to-get-rid-of-approval-wrapping](./we-want-to-get-rid-of-approval-wrapping.md) — two upstream paths (`deferred_tool_handler` and Traits `before_tool_call`) that would eliminate our ~440-line wrapping layer
- [blocking_approvals](./meta/blocking_approvals.md) — detailed `deferred_tool_handler` proposal we drafted for upstream
- [approvals-guard-against-llm-mistakes-not-active-attacks](./approvals-guard-against-llm-mistakes-not-active-attacks.md) — foundation: approvals are UX for catching LLM errors, not a security boundary
- [capability-based-approvals](./capability-based-approvals.md) — long-term direction: tools declare capabilities, runtime policy decides

## Traits API

- [pydanticai-traits-api-analysis](./pydanticai-traits-api-analysis.md) — analysis of the Traits API proposal (PR #4233) and what it means for llm-do: approval wrapping elimination and CallScope lifecycle replacement

## Broader comparison

- [llm-do-vs-pydanticai-runtime](./llm-do-vs-pydanticai-runtime.md) — what llm-do adds on top of vanilla PydanticAI: per-call isolation, approval wrapping, toolset factories, multi-agent orchestration

## Open threads

- **Stateful flag PR** — pending upstream. We support the proposal with caveats: require `copy()` override, enter lifecycle on copies, specify wrapper behavior.
- **deferred_tool_handler** — pending upstream. Blocked on [#3274](https://github.com/pydantic/pydantic-ai/issues/3274), [#3488](https://github.com/pydantic/pydantic-ai/issues/3488). Would be the fastest path to eliminating approval wrapping.
- **Traits API** — in research/design. Longer-term but could subsume both the stateful flag and approval wrapping.
- **Agent.run(toolsets=...)** — not proposed yet. Would decouple Agent construction from toolset binding, enabling Agent reuse across calls.

---

Topics:
- [index](./index.md)
