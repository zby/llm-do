---
description: Approvals are a UI feature for catching LLM errors, not a security boundary — isolation is the security boundary
areas: ["[[index]]"]
status: current
---

# approvals guard against LLM mistakes not active attacks

The attack surface of an LLM with tool access is too large for in-process approval gates to constitute a security mechanism. An adversarial or compromised LLM will find ways to breach any sandboxing that runs in the same process — through prompt injection, tool misuse, or exploiting inherent trust in tool outputs.

**Isolation is the security boundary.** Agents should run in containers or VMs. The host controls what gets pulled out. A complementary approach exists for LLM-authored code: [[pure-dynamic-tools]] achieves safety by restricting the execution sandbox to a single capability (`call_agent`), so that all side effects flow through agents with their own approval policies. Both patterns externalize security rather than relying on in-process gates.

**Approvals are a user interface feature.** Once you accept that isolation handles security, approvals serve two purposes:

1. **Visibility** — the user sees what the LLM is doing
2. **Error catching** — typos, wrong files, misunderstood instructions

Approvals do not protect against a determined attacker. They protect against an LLM that misunderstands your intent.

This distinction matters for design: since [[capability-based-approvals]] separates capability description from approval decisions, the approval pipeline can be tuned for usability (reducing friction for common operations) rather than for security (which would require defense-in-depth paranoia). And since [[container-security-boundary]] proposes containers as the single security mechanism, approvals don't need to duplicate that function.

This framing also clarifies why [[approval-override-rationale]] can focus on reducing prompt fatigue rather than enforcing security boundaries — per-agent overrides are a UX tuning mechanism, not a trust decision. Similarly, [[ui-event-stream-blocking-approvals]] designs timeout, redaction, and "remember" semantics as UX affordances rather than security gates.

The pragmatic reality is that many users run harnesses directly on their machines without isolation. Approvals still provide value as a speed bump in that scenario — just not a guarantee. The system should work in both modes without pretending approvals are something they're not. The [[execution-modes-user-stories]] concretize this across headless automation, interactive chat, and nested delegation scenarios, all of which treat approvals as usability affordances (session-level caching, per-tool preapproval, scoped grants) rather than security gates.

This framing also shapes the computational model: [[llm-do-vs-pydanticai-runtime]] describes tool calls as "syscalls" with interception points, where the runtime can approve, reject, or log them. The interception serves visibility and error-catching, consistent with approvals being a UX feature — the runtime mediates tool access for usability, while isolation handles the actual trust boundary.

---

Relevant Notes:
- [[capability-based-approvals]] — foundation: the approval system designed around this principle
- [[container-security-boundary]] — enables: containers provide the actual security boundary
- [[preapproved-capability-scopes]] — extends: pre-approval is safe precisely because approvals aren't security-critical
- [[dynamic-agents-runtime-design]] — context: dynamic agents widen the attack surface further, reinforcing the need for isolation
- [[approval-override-rationale]] — extends: per-agent overrides are safe to simplify because approvals are UX, not security
- [[ui-event-stream-blocking-approvals]] — grounds: the broker's timeout/redaction/remember design follows from approvals being a UX feature
- [[pure-dynamic-tools]] — enables: the RestrictedPython sandbox is a complementary safety model that externalizes security via capability restriction rather than in-process approval
- [[execution-modes-user-stories]] — example: approval scenarios 1-11 treat approvals as UX affordances (session caching, per-tool preapproval, scoped grants)
- [[llm-do-vs-pydanticai-runtime]] — extends: the "syscall interception" computational model frames approvals as mediation for visibility and error-catching, not security

Topics:
- [[index]]
