# OAuth Pro Account Logins

## Status
information gathering

## Prerequisites
- [ ] Decide how to represent "OpenAI pro" login (API key storage vs other) or capture the question in a note

## Goal
Add login flows for Anthropic Pro/Max and Google (Gemini CLI + Antigravity) aligned with pi-mono, plus a clear OpenAI pro account approach.

## Context
- Relevant files/symbols:
  - `llm_do/oauth/anthropic.py`
  - `llm_do/oauth/__init__.py`
  - `llm_do/oauth/storage.py`
  - `llm_do/cli/oauth.py`
  - `docs/cli.md`
- How to verify / reproduce:
  - `llm-do-oauth login --provider anthropic` works today (only provider supported).
  - New providers should allow successful login and refresh, then be usable by the runtime.

## Decision Record
- Decision:
- Inputs:
- Options:
- Outcome:
- Follow-ups:

## Tasks
- [x] Compare `llm_do/oauth/anthropic.py` with pi-mono for any updates (expiry buffer, parsing, error handling) and decide what to port.
- [ ] Add Google OAuth flows:
  - `google-gemini-cli` PKCE + local callback server on `127.0.0.1:8085`.
  - `google-antigravity` PKCE + local callback server on `127.0.0.1:51121`, multi-endpoint project discovery, fallback project ID.
  - Store `project_id` and optional `email`, refresh tokens, and expires timestamps.
- [ ] Extend `llm_do/oauth/storage.py` provider union and serialization for Google providers (fields already exist, providers do not).
- [ ] Update `llm_do/oauth/__init__.py` to refresh/resolve Google tokens and to return API keys that include `projectId` (pi-mono uses JSON `{ token, projectId }`).
- [ ] Expand `llm_do/cli/oauth.py` to allow `google-gemini-cli` and `google-antigravity` selection, with appropriate prompts/instructions.
- [ ] Decide how OpenAI "pro login" should work (likely API key storage helper or documented env var flow) and implement/update docs accordingly.
- [ ] Update `docs/cli.md` to document the added providers and login flows.
- [ ] Add targeted tests for new OAuth flows (token refresh, storage round-trip) if feasible without live network calls.

## Current State
Anthropic OAuth login exists and is CLI-accessible via `llm-do-oauth`, but only the `anthropic` provider is supported. Google and OpenAI login support is not implemented.

## Notes
- Anthropic flow deltas to apply:
  - Endpoints, client id, redirect URI, scopes, and code parsing match.
  - Subtract a 5-minute buffer from `expires_in`; llm-do currently stores the raw expiry.
  - Consider aligning storage behavior (return credentials without persisting) if desired; current llm-do persists immediately and includes `type="oauth"` in storage.
  - Error handling and state usage are otherwise aligned.
- Google OAuth expectations:
  - Both providers use PKCE auth-code flow with local HTTP callback servers (Gemini CLI: 127.0.0.1:8085, Antigravity: 127.0.0.1:51121).
  - Persist `project_id` and optional `email` from userinfo; refresh tokens should preserve prior refresh if absent.
  - API key should be JSON `{ token, projectId }` for downstream provider usage.
- opencode check:
  - No built-in OpenAI Pro OAuth in core; auth is plugin-driven via `ProviderAuth` and `/provider/{providerID}/oauth/*` endpoints.
  - The docs point to an external plugin `opencode-openai-codex-auth` for ChatGPT Plus/Pro usage (not shipped in repo).
  - Default bundled auth plugins are `opencode-copilot-auth` and `opencode-anthropic-auth` (no Google/OpenAI by default).
  - Auth storage is unified (`auth.json`) with `type: "oauth"` or `type: "api"`, and OAuth flows support `method: "auto"` or `method: "code"` callbacks.
