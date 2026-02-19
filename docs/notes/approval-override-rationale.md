---
description: Why per-agent approval overrides exist and when we might remove them
areas: [approvals-index]
---

# Approval Override Rationale

## Context
We currently support global approval flags for agent tool calls and attachments, plus per-agent overrides. This note captures why overrides exist and the conditions under which we could remove them to simplify the runtime configuration surface.

## Why overrides exist
Per-agent overrides allow policy exceptions when global defaults are too coarse.

Common scenarios:
- **High‑risk agent exceptions:** Global approvals are off for speed, but a dangerous agent (e.g. deployer, filesystem cleaner, external API caller) should always require approval.
- **Low‑risk agent exceptions:** Global approvals are on for safety, but harmless agents (e.g. summarizer/classifier) should be auto‑approved to reduce prompt fatigue.
- **Attachment sensitivity:** Only agents that accept attachments (or could leak data) should prompt on attachments.
- **Delegation control:** Recursive or delegated calls may need stricter approvals for specific child agents.

## If we remove overrides
We would keep only:
- `agent_calls_require_approval`
- `agent_attachments_require_approval`

That simplifies runtime config but loses the ability to express exceptions. It forces the system into either “approve everything” or “approve nothing” at the agent‑tool level, which is too coarse for mixed‑risk workloads.

## Candidate simplifications
- **Keep overrides but collapse shapes:** Use a single schema for overrides (Pydantic or dataclass) and remove normalization glue.
- **Remove overrides entirely:** If the product direction is minimal config and we can accept coarse policy.

## Open Questions
- Are there concrete users or workflows relying on per‑agent exceptions today?
- Should attachment approvals be a separate concern from agent call approvals, or tied together?
- If overrides stay, should the canonical shape be Pydantic (shared with manifest) or a runtime dataclass?
- Is there a different policy model (capability-based) that would replace per‑agent overrides entirely? (See [capability-based-approvals](./capability-based-approvals.md) — tools declare capabilities, runtime policy evaluates them, making per-agent overrides unnecessary.)

---

Relevant Notes:
- [approvals-guard-against-llm-mistakes-not-active-attacks](./approvals-guard-against-llm-mistakes-not-active-attacks.md) — grounds: since approvals are UX rather than security, override simplification is a usability question, not a safety one
- [capability-based-approvals](./capability-based-approvals.md) — supersedes: capability-based policy where tools declare facts and the runtime evaluates them replaces the need for per-agent approval overrides
