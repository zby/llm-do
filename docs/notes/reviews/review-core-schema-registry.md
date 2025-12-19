# Core Schema and Registry Review

## Context
Review of core data models, registry loading/saving, config overrides, and model compatibility for correctness and consistency.

## Findings
- `apply_set_override` treats existing non-dict values as errors, so `--set toolsets.delegation.foo={}` fails when `toolsets` is `None` (default). This makes nested overrides unexpectedly fragile unless the caller first sets `toolsets={}` explicitly.
- `WorkerContext.creation_defaults` is optional but `DelegationToolset.worker_create` assumes it is present and passes it into `create_worker` without a guard; custom callers constructing `WorkerContext` directly can trigger a `TypeError`.
- `WorkerRegistry._definitions_cache` never invalidates; long-lived processes that save or reload definitions can serve stale configs (especially after CLI overrides are injected).

## Analysis
- Nested override UX is brittle because callers must pre-seed intermediate dicts, which is not obvious and makes CLI overrides feel inconsistent with typical `--set` behavior.
- The `creation_defaults` mismatch is an integration footgun: internal flows likely set it, but external integrations or tests that build `WorkerContext` manually can fail at runtime in a non-obvious location.
- A non-invalidating registry cache is fine for short-lived CLI runs, but in long-lived processes it can yield stale worker definitions after writes, reloads, or override updates.

## Possible Fixes
- For nested overrides:
  - Treat `None` as `{}` while descending into dict paths.
  - Alternatively, allow a `--set` mode that auto-creates intermediate dicts (and document it).
- For `creation_defaults`:
  - Make it required with a default instance, or
  - Add a guard in `worker_create` that uses a safe default when missing and logs a warning.
- For registry caching:
  - Invalidate cache entries on `save_definition`/`reload` operations, or
  - Provide an explicit `refresh`/`clear_cache` API and use it in long-lived flows.

## Recommendations
1. Make `apply_set_override` treat `None` as `{}` to remove the two-step override requirement.
2. Ensure `WorkerContext.creation_defaults` is always set (required field or safe default in toolset).
3. Add cache invalidation hooks so registry reads reflect recent writes in long-running sessions.

## Open Questions
- Should `apply_set_override` treat `None` as an empty dict to support nested overrides without a two-step `--set`?
- Should `WorkerContext.creation_defaults` be required (non-optional) to avoid tool-time failures?
- Is the registry cache meant to be ephemeral per CLI invocation only, or should it support invalidation on save/reload?

## Conclusion
The issues are small but high-impact for integration reliability and override UX. Prioritize the override fix and `creation_defaults` safety, then add cache invalidation to prevent stale registry reads.
