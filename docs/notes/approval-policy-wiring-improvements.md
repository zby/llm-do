# Approval Policy Wiring Improvements After 932fa04

## Context
Commit 932fa04 moved approval wrapping from a recursive run-boundary pass to per-worker call time.
That simplified the mental model but added wiring: RunApprovalPolicy was threaded through the
runtime so nested workers can resolve approvals, ToolInvocable entries still get wrapped at the
run boundary, and tests/docs grew. This note explores ways to reduce that code while keeping the
same behavior.

## Findings
Option A: Resolve once per run and store a WorkerApprovalPolicy (or just approval_callback) in RuntimeConfig.
- How: In run_entry, call resolve_worker_policy(approval_policy) once; pass WorkerApprovalPolicy
  into WorkerRuntime.from_entry. Expose ctx.worker_approval_policy or ctx.approval_callback, not
  ctx.run_approval_policy. Worker.call uses the resolved policy directly.
- Pros: Removes RunApprovalPolicy from WorkerRuntimeProtocol, eliminates repeated resolve on every
  Worker.call, keeps a single callback instance (and shared cache) per run.
- Cons: Loses easy access to the original RunApprovalPolicy (mode, cache_key_fn) unless stored
  separately; requires API changes and test updates.

Option B: Introduce a runtime Approvals/ApprovalManager object.
- How: Build an Approvals object once per run (approval_callback + return_permission_errors +
  wrap_toolsets). Store it in RuntimeConfig and expose ctx.approvals.
- Pros: Centralizes approval logic, hides RunApprovalPolicy/WorkerApprovalPolicy from most of the
  codebase, provides a single hook for future metrics or UI integration.
- Cons: New type to maintain; still requires wiring but slightly more indirection.

Option C: Remove wrap_entry_for_approval and gate ToolInvocable entries inside WorkerRuntime._execute.
- How: When entry.kind is tool_invocable, wrap its toolsets using ctx.approvals before building
  child_ctx. Then drop run_entry's special-case wrap_entry_for_approval.
- Pros: All wrapping happens at execution time; fewer exported helpers and less run-boundary
  special casing.
- Cons: ToolInvocable entries no longer wrapped until execution; must ensure ctx.deps.call still
  sees wrapped toolsets and avoid double-wrapping.

Option D: Precompute wrapped toolsets once per runtime/entry.
- How: Compute approval-wrapped toolsets once when building the runtime (or once per Worker.call
  and cache on the child ctx), then reuse for the agent and tool dispatch.
- Pros: Fewer allocations and repeated wraps; ensures consistent callback for a run.
- Cons: Slightly more stateful; needs care if toolsets mutate or if a worker is reused across runs.

Option E: Replace ToolsetRef with a binding structure that carries approval config.
- How: Instead of ToolsetRef wrappers, store ToolsetBinding {toolset, approval_config} in Worker
  toolsets, and feed config directly into ApprovalToolset at wrap time.
- Pros: Removes an extra wrapper class and __getattr__ proxying; clearer ownership of per-worker
  approval config.
- Cons: Requires broader type changes (Worker.toolsets, loader, call sites) and more refactoring.

Option F: Keep RunApprovalPolicy but avoid threading it through WorkerRuntimeProtocol.
- How: Store RunApprovalPolicy privately in RuntimeConfig and expose only what callers need
  (approval_callback/return_permission_errors). Protocol can stay minimal.
- Pros: Shrinks the public runtime surface without changing high-level behavior.
- Cons: Some duplication if other layers still need the full policy.

## Open Questions
- Is preserving direct access to RunApprovalPolicy (mode/caching settings) in nested workers a
  requirement, or can we switch to exposing only a resolved approval callback/policy?
- Should ToolInvocable wrapping move into WorkerRuntime._execute to eliminate wrap_entry_for_approval,
  or is the explicit run-boundary hook preferred for clarity?
- Is it worth refactoring ToolsetRef into a binding structure, or is the wrapper overhead acceptable?
- Do we want a single callback instance per run by default (to share caching), even when
  RunApprovalPolicy.cache is None?

## Conclusion
