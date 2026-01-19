# Capability-Based Approvals for Toolsets and Workers

## Context
Deep dive after the decomplect review on approval boundaries across toolsets,
workers-as-tools, and runtime policy. Goal: reconcile local semantic knowledge
(toolset authors) with global environment rules (isolated vs real), while
reducing ambiguity in "who decides" approval.

## Assumptions
- The system is intended to run in strong isolation (VM or container).
- Approval is UX, not a security boundary; safety comes from isolation and guardrails (no pushes, restricted host access).
- People will still run unisolated or with weak isolation, so policy must handle an "unknown" profile explicitly.

## Findings
- Current approval logic is distributed across runtime wrappers, toolset
  hooks, and WorkerToolset overrides, making decisions hard to explain and test.
- Toolset authors know semantic risk (what a call does); runtime knows
  environment risk (isolated vs real). We need both local and global rules.
- Capability-based approvals provide a clean split:
  - Toolsets return required capabilities per call (local semantics).
  - Runtime provides granted capabilities per environment; missing caps require
    approval (global rules).
- Approval policy should model two axes explicitly:
  - Isolation profile: isolated vs unisolated/unknown (safety net strength).
  - Interaction mode: approve_all, prompt, reject_all (UX choice).
- Persistent capability grants across calls are simplest for UX; store per
  worker run and optionally inherit to child workers (subset of parent grants).
- Isolated mode granting all capabilities is a user choice for low-risk work;
  keep it explicit and log sensitive actions even when auto-granted.
- If isolation or guardrails are missing, treat the profile as unknown and
  default to prompt or reject; do not let "remember" override hard denies.
- Approval evaluation should be centralized in runtime: toolsets describe,
  runtime decides. Avoid multiple layers deciding separately.
- `return_permission_errors` should be treated as transport (exception vs
  result), not part of approval policy.
- Attachments: approval can be based on intent (args) before validation; this is
  conservative but introduces a TOCTOU gap. If needed later, validate after I/O
  or re-evaluate for higher-risk contexts.
- Capability granularity is a major lever. Start coarse (e.g., `fs.write`,
  `net.external`, `data.user`) and evolve as needed to avoid prompt overload.
- "Remember" is a UX cache, not policy; it should be easy to clear and scoped
  to a stable isolation profile.

## Open Questions
- Capability taxonomy: what is the minimal stable set, and how do we name/extend it?
- Grant lifetime and scope: per worker run is agreed, but how should grants flow
  to nested worker calls?
- Should any capabilities be non-waivable even in isolated mode (e.g., external
  network), or is isolated always "grant all" when the user opts in?
- Do we want parameterized capabilities (path-scoped, attachment size limits) or
  keep them as plain strings for v1?
- Attachment approvals: is intent-level approval sufficient, or do we want
  post-validation re-checks in non-isolated contexts?
- UI: is showing raw capability names acceptable for v1, or do we need a
  minimal human-readable mapping?
- How is isolation profile detected or configured (manifest, CLI flag, runtime default)?
