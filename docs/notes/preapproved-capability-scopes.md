---
description: Path-scoped preapproval policies for reducing approval prompts
---

# Preapproved Capability Scopes

## Context
Approvals today are per-tool-call. This is safe but can be noisy for common
operations (especially file reads/writes). A scoped preapproval policy could
reduce prompts while keeping a default-deny posture. This note captures the
idea; it is out of scope for immediate implementation.

## Findings
- A capability policy can be expressed as rules that map an operation to one of:
  allow (no prompt), require_approval (prompt), or deny. This could live in a
  run-level policy object and be enforced by toolsets in `needs_approval()`.
- Path-scoped file rules are the most immediate payoff:
  - Example 1: allow reads everywhere, require approval for all writes except
    `/home/zby/llm/llm-do/` (writes there are allowed).
  - Example 2: allow any edit in `/home/zby/llm/llm-do/`, but require approval in
    `/home/zby/llm/llm-do/secrets/`.
  - The above requires a clear precedence model (more specific path wins, or
    explicit rule priority ordering).
- Rules should be explicit about action type (read vs write vs delete) and scope
  (path prefix, glob, or tool category). This prevents "allow write" from
  accidentally granting read or delete.
- A consistent rule resolution strategy avoids ambiguity:
  - Option A: most specific path match wins; ties break by rule order.
  - Option B: explicit priority; if not set, deny > require_approval > allow.
- The approval UI could offer scoped escalation shortcuts:
  - "Allow writes in this directory for this run"
  - "Always require approval in this subdirectory"
  These would append rules to the session policy rather than approving a single
  tool call.
- This policy should integrate with existing `_approval_config` (per tool) and
  toolset-specific `needs_approval()` logic. Rule evaluation should happen
  before tool-specific heuristics to keep the security boundary centralized.

## Open Questions
- Rule format: YAML in worker config, CLI flags, or a separate policy file?
- Persistence: per-run only, or allow opt-in persistence across runs?
- Precedence: is "more specific path wins" enough, or do we need explicit
  priorities and a three-way decision (allow / prompt / deny)?
- How should path scope interact with non-filesystem tools (shell/network)?
- Do we need a deny state, or is "require approval" sufficient for all
  disallowed operations?

