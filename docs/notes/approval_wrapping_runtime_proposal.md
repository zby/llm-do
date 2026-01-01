# Approval Wrapping Location (CLI vs Runtime)

## Context
Current approval wrapping happens in `llm_do/ctx_runtime/cli.py`, which means
programmatic users (direct Python runs) must duplicate CLI logic to keep the
same approval behavior. The recent class-path toolset work also makes the
wrapping location more visible. This note analyzes whether wrapping should move
into runtime and sketches a concrete design.

## Findings
- Current flow: `build_entry()` resolves toolsets and returns a raw entry; `run()`
  wraps toolsets via `_wrap_toolsets_with_approval()` and then builds
  `WorkerRuntime`. Runtime itself does not wrap.
- CLI owns approval mode (approve-all/reject-all, TUI callback) so the wrapping
  lives where the policy is known. Moving into runtime requires threading that
  policy through runtime APIs.
- UX: runtime-owned wrapping makes programmatic usage consistent with CLI and
  removes boilerplate in experiments and custom runners.
- Security: approval is a safety boundary. Centralizing in runtime reduces the
  risk of forgetting to wrap, but it also means runtime must decide what to do
  when approval policy is absent.
- Coupling: runtime becomes aware of approval UI (callbacks, error formatting),
  which may be acceptable if approvals are considered a core execution concern.
- Recursion: workers can contain toolsets; wrapping must recurse into nested
  `WorkerInvocable.toolsets`. Pre-wrapped toolsets complicate recursion and can
  hide inner toolsets from additional wrapping.
- Consistency: `return_permission_errors` behavior should be identical across
  CLI and programmatic runs; a shared helper avoids divergent behavior.
- Overengineering risk: introducing a generic "middleware pipeline" for
  toolsets might be premature unless other wrappers (tracing, caching) are
  imminent.

## Design Proposal
Introduce a small approval policy object and move wrapping into runtime, while
keeping CLI as the policy builder.

1. New approval policy dataclass (runtime-level).
   - Example fields: `approval_callback`, `return_permission_errors`,
     `memory` (optional), `mode` ("headless", "interactive").
2. Shared helper for wrapping.
   - Move `_wrap_toolsets_with_approval()` into a runtime module
     (e.g., `llm_do/ctx_runtime/approval.py`) and expose:
     - `wrap_toolsets_for_approval(toolsets, policy) -> list[AbstractToolset]`
     - `wrap_entry_for_approval(entry, policy) -> entry`
   - Always recurse into `WorkerInvocable.toolsets`.
   - If an `ApprovalToolset` is already present, prefer to skip re-wrapping but
     still ensure nested toolsets are wrapped (possible by unwrapping via
     `inner` attribute if available, or by documenting "do not pre-wrap").
3. Runtime API change.
   - Add `approval_policy: ApprovalPolicy | None` to
     `WorkerRuntime.from_entry()` (and/or `WorkerRuntime.__init__`).
   - If policy is provided, runtime wraps entry toolsets before any agent is
     built. If not, runtime leaves toolsets untouched.
4. CLI integration.
   - `run()` constructs `ApprovalPolicy` from `approve_all`, `reject_all`, or
     TUI callback and calls `WorkerRuntime.from_entry(..., approval_policy=...)`.
   - CLI no longer performs wrapping itself.

## Open Questions
- Should runtime always require an approval policy (fail closed) or allow
  `None` for raw toolsets (opt-out for tests and power users)?
- Do we support pre-wrapped toolsets, or is "runtime owns wrapping" a hard
  rule?
- Should `ApprovalToolset` remain the mechanism, or is it time to move approval
  into `WorkerRuntime.call_tool()` directly?
- Where should `ApprovalMemory` live: per-run policy instance, or global?
- Is a future wrapper pipeline needed (logging/tracing), or would that be YAGNI?

## Conclusion
(pending)
