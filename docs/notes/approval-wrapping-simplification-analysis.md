# Approval Wrapping Simplification Analysis

## Context
Analysis of commit `932fa04f2cf718695d485d4ccf65aad609b3639a` (implemented simplification of wrapping) and the preceding context. Goal: explain why the simpler "wrap per worker at call time" model was not implemented from the start, and why the earlier recursive wrapping path was misleading.

## Findings
- The original architecture placed approval policy at the run boundary, so the obvious hook was "wrap the entry and recurse through toolsets." That is exactly what `_wrap_toolsets_with_approval` in `llm_do/runtime/approval.py` did before `932fa04f2c...`.
- There was no way for `Worker.call` to access the run policy until `RunApprovalPolicy` was stored on `WorkerRuntime`. Without that, per-worker wrapping at call time was not viable, which pushed the design toward recursive wrapping at the boundary.
- Early design notes advocated a recursive approval wrapper as a simplification for direct-run scripts (see `docs/notes/v2_direct_run_simplification.md`), reinforcing the "tree transform" mental model.
- Per-worker approval config (`_approval_config`) was already problematic for shared toolset instances. The `ToolsetRef` wrapper was introduced to avoid shared-state mutation, but that wrapper hides `Worker` type checks. This made recursive wrapping more complex (needing to unwrap) and further entrenched the recursive approach.
- Recursive wrapping was misleading because it treats workers as static toolset nodes rather than execution boundaries. It forces a static tree transform to enforce a dynamic, per-run policy.
- The recursion also created brittle behavior:
  - Multiple wrappers could exist for the same underlying callable while exposing identical tool schemas, making the policy boundary ambiguous.
  - Cycle handling and "already wrapped" checks were necessary, which are symptoms of applying a dynamic policy via a static transformation.
  - Shared toolsets risked policy leakage when wrapped at the boundary rather than at worker call time.
- The `932fa04f2c...` change becomes possible only after the run policy is part of runtime context, so workers can wrap their own toolsets deterministically when they build their agent.

## Open Questions
- Should the "global base invocable registry + per-worker wrapping" idea from `docs/notes/invocables-wrapping-mental-model.md` be implemented to further simplify tool assembly?
- Should `ToolInvocable` entry gating remain fixed to "entry call is trusted" or become configurable per run/entry?
- Is there any remaining flow that still depends on pre-wrapped toolsets (beyond tests/live helpers), and should that be explicitly disallowed or supported?

## Conclusion
The recursive approval wrapper was a natural early choice because approval policy lived only at the run boundary, and workers were treated as static toolsets. As runtime context gained a run-level policy and per-worker configuration became important, the recursion became a liability. The `932fa04f2c...` refactor corrects the boundary: workers now wrap their own toolsets at call time, making approval policy deterministic, local, and cycle-safe.
