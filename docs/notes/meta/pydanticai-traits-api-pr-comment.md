---
description: Comment posted on pydantic-ai PR #4233 (Traits API research report)
date: 2026-02-16
pr: https://github.com/pydantic/pydantic-ai/pull/4233
---

# Comment on PydanticAI Traits API PR

Great research report. We've been building [**llm-do**](https://github.com/zby/llm-do) on top of pydantic-ai and have independently converged on several of the patterns described here. Thought it might be useful as a real-world validation point.

## Where we overlap

**Agent-as-tool composition.** Our `AgentToolset` wraps an `AgentSpec` as an `AbstractToolset`, so the calling LLM sees child agents as ordinary tools. The toolset wrapper itself is straightforward — the real complexity lives in the lifecycle and registry layers around it: call-scoped state isolation, depth tracking, toolset preparation/teardown, and name-based resolution across agent/tool registries. This is essentially what `SubAgentTrait` describes. We don't have agent handoff yet but would like to — the report's `HandoffTrait` is interesting because it would need to address the same lifecycle questions we've been working through. ([`llm_do/toolsets/agent.py`](https://github.com/zby/llm-do/blob/main/llm_do/toolsets/agent.py), [`llm_do/runtime/context.py`](https://github.com/zby/llm-do/blob/main/llm_do/runtime/context.py), [`llm_do/runtime/call.py`](https://github.com/zby/llm-do/blob/main/llm_do/runtime/call.py))

**Name-based registry.** Our [`Runtime`](https://github.com/zby/llm-do/blob/main/llm_do/runtime/runtime.py) holds separate registries for agents, tools, and toolsets — all resolved by name. A `RegistryProtocol` defines the contract (also in `runtime.py`), and the runtime populates it from project manifests. [`CallContext`](https://github.com/zby/llm-do/blob/main/llm_do/runtime/context.py) exposes these registries to running agents, so any tool can look up and invoke other agents or tools by name. This is how we enable what we call "crystallisation" — gradually moving stable logic from LLM prompts into deterministic Python tools without changing call sites. The trait catalog's dependency resolution (`requires`, `conflicts_with`) would interact with something like this.

**Approval gates as a cross-cutting concern.** We currently wrap every toolset with approval logic at the `CallScope` boundary — toolsets declare `needs_approval()` / `get_approval_description()`, and the runtime intercepts before execution. But we're designing a [capability-based approval system](https://github.com/zby/llm-do/blob/main/docs/notes/capability-based-approvals.md) that separates **description from decision**: tools declare required capabilities (`fs.write`, `net.egress`, `proc.exec`), and the runtime holds a single policy that maps those capabilities to approval levels. The Traits API's guardrail model — with `check_input()` / `check_output()` and the tripwire/transform/warn actions — maps naturally onto this. `ApprovalTrait` as proposed in the report is close to what we need, but the capability-based framing pushes further: traits wouldn't make approval decisions themselves, they'd declare capability requirements, and a single runtime policy would decide. ([`docs/notes/capability-based-approvals.md`](https://github.com/zby/llm-do/blob/main/docs/notes/capability-based-approvals.md))

**Declarative agent definitions.** We use `.agent` files (YAML frontmatter + system prompt) linked via a `project.json` manifest, similar to the YAML serialization proposed in the report.

**Call-scoped lifecycle.** Our `CallScope` / `CallFrame` / `CallContext` stack manages per-call isolation, depth limits, toolset preparation, and cleanup — essentially the `on_agent_start` / `on_agent_end` lifecycle hooks, but expressed as context managers. This is the largest chunk of code we maintain on top of pydantic-ai. If traits formalized this lifecycle, we could delete a significant portion of our lifecycle scaffolding.

## Observations

**Capability declarations > per-trait approval logic.** The report shows `ApprovalTrait(mode="writes")` wrapping other traits. We'd argue for something lower-level: let each trait/toolset declare the capabilities it requires per call, and let one runtime policy interpret them. This avoids every trait reimplementing its own approval reasoning and makes policy changes a single-point concern.

**`AbstractToolset` already gets you surprisingly far.** Tools, approval hooks, dynamic instantiation — the toolset interface handles most of what we need. The gap is call-scoped state management (depth, message isolation, toolset teardown), which is exactly what the lifecycle hooks in this proposal would address. That's the part we'd most like to stop maintaining ourselves.

---

If it's useful, llm-do could serve as a testbed for validating trait designs against a real orchestration layer. We're tightly coupled to `AbstractToolset`, `Agent`, `RunContext`, and the message/event types already — anything that lets us replace our own shims with framework primitives is a win, regardless of what it does to our current API surface. Happy to try early APIs and report back on friction points.
