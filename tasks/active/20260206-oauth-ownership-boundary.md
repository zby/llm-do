# OAuth Ownership Boundary for Package Split

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Decide and implement where OAuth model override behavior belongs (`core runtime` vs `app/harness`) so the package split can proceed without hidden cross-layer coupling.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/agent_runner.py` (`run_agent`, OAuth resolution path)
  - `llm_do/runtime/runtime.py` (`RuntimeConfig.auth_mode`)
  - `llm_do/runtime/manifest.py` (`ManifestRuntimeConfig.auth_mode`)
  - `llm_do/oauth/__init__.py` (`get_oauth_provider_for_model_provider`, `resolve_oauth_overrides`)
  - `llm_do/cli/main.py` (manifest-driven runtime construction)
- Related tasks/notes/docs:
  - `tasks/active/20260206-package-split-runtime-project-harness.md`
  - `tasks/completed/52-oauth-storage-dependency-injection.md`
  - `docs/architecture.md` (runtime/harness layering)
- Validated current state (2026-02-06):
  - Runtime directly imports OAuth helpers in `agent_runner.py`, so core execution currently depends on host OAuth implementation.
  - Runtime config and manifest schema both expose `auth_mode`, so auth policy is already part of runtime-facing contract.
  - OAuth CLI and provider-specific logic live outside runtime in `llm_do/oauth/*` and `llm_do/cli/oauth.py`.
- How to verify / reproduce:
  - `rg -n "from \.\.oauth|resolve_oauth_overrides|get_oauth_provider_for_model_provider" llm_do/runtime`
  - `uv run pytest tests/runtime/test_oauth_runtime.py tests/test_oauth_anthropic.py tests/runtime/test_manifest.py`
  - `uv run ruff check .`
  - `uv run mypy llm_do`

## Decision Record
- Decision:
  - Pending; resolve in this task.
- Inputs:
  - Package split requires clean dependency direction and embeddable core runtime.
  - Existing behavior for `auth_mode` and OAuth override resolution must remain stable for users.
- Options:
  - A) Keep OAuth resolution in runtime (status quo) and treat OAuth as a core dependency.
  - B) Introduce an injected auth resolver seam (protocol/callback) so runtime is auth-provider agnostic, with app/harness wiring OAuth implementation.
- Outcome:
  - TBD in this task (record selected option and rationale).
- Follow-ups:
  - If Option B is chosen, update package split task module ownership and dependency checks accordingly.

## Tasks
- [ ] Time-box decision work and capture chosen option with explicit trade-offs in Decision Record.
- [ ] Implement minimal code change required by the chosen option (YAGNI; no broader auth redesign).
- [ ] Preserve existing `auth_mode` semantics (`oauth_off`, `oauth_auto`, `oauth_required`) and runtime behavior.
- [x] Add or update focused tests covering the chosen boundary and failure modes.
- [ ] Update `tasks/active/20260206-package-split-runtime-project-harness.md` prerequisite checkbox once resolved.

## Current State
Created as a prerequisite gate for the package split. Dependency and coupling are validated; ownership decision and implementation are pending.
Focused runtime-level OAuth coverage is now in place via `tests/runtime/test_oauth_runtime.py`:
- `oauth_auto` path uses OAuth model override when available.
- `oauth_required` path raises when overrides/credentials are unavailable.
Verification command was updated to use this new targeted runtime test instead of a `-k oauth` filter that selected zero tests.

## Notes
- Keep this task narrow: boundary ownership only.
- Do not change OAuth provider feature scope in this task.
