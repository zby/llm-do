# ADR-001: Thin Custom Prefix Adapter + OAuth Gating

**Status:** Accepted

**Date:** 2026-02-01

## Context

`llm-do` currently supports custom model prefixes via a local registry (`register_model_factory`), while
PydanticAI already provides model inference for all built-in providers. We want to:

- Rely on PydanticAI for standard provider resolution.
- Keep only a minimal extension hook for non-standard prefixes.
- Add an explicit, manifest-driven switch for OAuth usage so projects opt in and examples stay stable.
- Validate this approach in `llm-do` before proposing an upstream extension API in PydanticAI.

## Decision

- Keep a **thin custom-prefix adapter** for model resolution:
  - If a model string uses a custom prefix that is registered, we resolve it locally.
  - Otherwise, delegate to `pydantic_ai.models.infer_model`.
  - Disallow registering prefixes that PydanticAI already recognizes, to prevent shadowing built-ins.
- Add a manifest runtime switch `auth_mode` with values:
  - `oauth_off` (default)
  - `oauth_auto`
  - `oauth_required`
- Apply OAuth at runtime only when `auth_mode` permits it. OAuth overrides are resolved from the
  model identifier (string form) without leaking OAuth details into the rest of the runtime.
- Use this pattern as a proving ground for a future upstream extension API.

## Consequences

- The core model resolution path becomes PydanticAI-first, reducing local surface area.
- Custom prefixes remain possible but explicitly limited to non-standard providers.
- OAuth becomes an explicit project-level policy, avoiding accidental behavior changes.
- `AgentSpec` must carry a `model_id` (original string) so the runtime can resolve OAuth overrides.
- We can propose an upstream extension API after validating the ergonomics internally.
