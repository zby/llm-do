# Headless Tool Exposure Filter

## Idea
In headless runs without approvals, avoid advertising tools that will always be
rejected by the approval policy.

## Why
Reduces failed tool calls in automation and aligns tool exposure with what can
actually succeed (fewer confusing PermissionError results).

## Rough Scope
- Add a lightweight "exposure policy" derived from `ApprovalPolicy` at the run
  boundary (headless + no approve-all -> preapproved-only exposure).
- Teach toolsets to optionally report which tools are preapproved in their
  current config (filesystem, shell first; unknown toolsets default to
  conservative behavior).
- Filter tool definitions before agent construction based on exposure policy.
- Add tests covering headless runs: only preapproved tools are exposed.

## Why Not Now
Approval system already blocks; no current requirement to change exposure.

## Trigger to Activate
Headless/automation users report repeated failed tool calls or confusion about
why tools are advertised but unusable.
