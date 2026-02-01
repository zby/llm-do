# ADR-001: Thin Custom Prefix Adapter + OAuth Gating

**Status:** Accepted

**Date:** 2026-02-01

## Context

### Why String-Based Model Selection?

PydanticAI allows users to configure model objects directly in code:

```python
from pydantic_ai.models.anthropic import AnthropicModel

model = AnthropicModel("claude-3-5-haiku-latest", api_key="...")
agent = Agent(model=model, ...)
```

However, llm-do is a **library/CLI tool** where we want simple, declarative configuration. We chose string-based model selectors (e.g., `anthropic:claude-haiku-4-5`) that can be:
- Passed via the `LLM_DO_MODEL` environment variable
- Specified in `.agent` files or `project.json`
- Overridden at runtime without code changes

This simplicity creates a need: **how do we support custom providers** (e.g., a company's internal API gateway, a local model server) that aren't in PydanticAI's built-in provider list?

### The Extension Problem

PydanticAI's `infer_model()` handles built-in providers (`anthropic:`, `openai:`, `gemini:`, etc.) but has no extension mechanism for custom prefixes. We need a way to register custom providers while:
- Relying on PydanticAI for standard providers (no duplication)
- Keeping the extension surface minimal
- Preventing accidental shadowing of built-in providers

### OAuth Complexity

Some custom providers require OAuth authentication. We want OAuth to be:
- Explicit and opt-in (not silently enabled)
- Project-level policy (in manifest), not per-agent
- Isolated from the core runtime

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
