---
description: Approval system design — threat model, capability taxonomy, UI integration, and upstream simplification
type: moc
---

# Approvals

The approval system is a usability feature, not a security boundary. Since [approvals guard against LLM mistakes not active attacks](./approvals-guard-against-llm-mistakes-not-active-attacks.md), the design optimises for reducing friction (fewer prompts, scoped preapprovals) rather than achieving isolation (which belongs to containers and process boundaries). The central tension is between safety and noise: every approval prompt is an interruption, but every skipped prompt is a trust decision.

## Notes

- [approvals-guard-against-llm-mistakes-not-active-attacks](./approvals-guard-against-llm-mistakes-not-active-attacks.md) — the foundational threat model: approvals catch errors, isolation stops attacks
- [capability-based-approvals](./capability-based-approvals.md) — capability taxonomy (`fs.write`, `net.egress`) as the mechanism for structured approval decisions
- [preapproved-capability-scopes](./preapproved-capability-scopes.md) — path-scoped preapproval policies to reduce prompt noise while keeping default-deny
- [approval-override-rationale](./approval-override-rationale.md) — why per-agent overrides exist and conditions for removing them
- [ui-event-stream-blocking-approvals](./ui-event-stream-blocking-approvals.md) — how blocking approvals work when UI is decoupled from the runtime event stream
- [we-want-to-get-rid-of-approval-wrapping](./we-want-to-get-rid-of-approval-wrapping.md) — upstream PydanticAI paths to eliminate the ApprovalToolset wrapper stacking
- [pydanticai-traits-api-analysis](./pydanticai-traits-api-analysis.md) — analysis of the Traits API proposal: one of the two paths to eliminating wrapping, plus potential CallScope replacement

## Open Questions

- How do approvals compose with dynamic agents? If a subagent creates tools at runtime, who approves them?
- What's the right default preapproval scope for interactive vs scripted execution modes?
