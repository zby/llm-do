# Per-Worker Approval Config Semantics

## Context
Per-worker `_approval_config` must not mutate shared toolset instances when
multiple workers reuse the same Python toolset. We need per-reference semantics
without introducing extra toolset wrapper types.

## Findings
- `_approval_config` originates in the worker YAML and is extracted when the
  worker is built.
- The worker stores a parallel list of approval configs aligned with its
  `toolsets`.
- `WorkerApprovalPolicy.wrap_toolsets(...)` now consumes the explicit config
  list instead of reading attributes on toolset instances.
- Shared toolset refs allow `_approval_config` only; other keys remain invalid.

## Open Questions
- None.

## Conclusion
Store per-worker approval config directly on the `Worker` and pass it into
approval wrapping. This removes the need for `ToolsetRef` while preserving
per-reference semantics for `_approval_config`.
