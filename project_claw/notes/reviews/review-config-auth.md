---
description: Periodic review findings for config and auth modules.
---

# Config and Auth Review

## Context
Review of config and auth modules for bugs, inconsistencies, and overengineering.

## Findings
- `--set` overrides are fairly robust: supports dot paths and bracketed literal
  keys (for class-path toolset keys), creates intermediate dicts, and parses
  JSON/booleans/numbers. (`llm_do/config.py`)
- Model selection behavior is internally consistent with the CLI’s intent (model
  override applies to the entry worker; nested workers keep their own `model`),
  but the docs/comments in `llm_do/models.py` disagree on precedence (CLI vs
  worker). This is a documentation/expectation footgun. (`llm_do/models.py`,
  `llm_do/cli/main.py`)
- OAuth storage is cleanly separated via an injected backend and writes the
  credential file with restrictive permissions (0600). (`llm_do/oauth/storage.py`)
- OAuth login/refresh flows don’t print tokens and keep sensitive values in the
  storage file, but token-exchange failures surface `response.text` in raised
  exceptions, which could include verbose provider error payloads. (`llm_do/oauth/anthropic.py`)
- OAuth “model override” support exists (`resolve_oauth_overrides`) and sets
  Anthropic beta headers (including `anthropic-dangerous-direct-browser-access`),
  but it is currently unused by the runtime/CLI, so `llm-do-oauth login` does
  not appear to affect `llm-do` runs yet. (`llm_do/oauth/__init__.py`,
  `llm_do/runtime/worker.py`, `llm_do/cli/main.py`)

## Open Questions
- Should `llm_do/models.py` docstrings be updated to reflect current precedence,
  or should precedence be changed to match the docs?
- Do we want `llm-do` to automatically use OAuth credentials when available for
  a provider (integrate `resolve_oauth_overrides`), or keep OAuth strictly
  opt-in?
- If OAuth integration is planned, what’s the policy for “dangerous direct
  browser access” headers and system prompt overrides?

## Conclusion
Config override ergonomics are in good shape, and OAuth storage is reasonably
safe, but the model-selection docs are inconsistent and OAuth integration into
the main runtime appears incomplete.

## Review 2026-02-01

### Findings
- **Empty LLM_DO_MODEL treated as a real model id:** `get_env_model()` returns the raw env value; if it's empty/whitespace, `select_model_with_id()` treats it as a model id and defers failure to `infer_model`, yielding confusing errors. Normalize empty values or raise a targeted error. (`llm_do/models.py`)
- **OAuth auto requires explicit provider prefixes:** `resolve_oauth_overrides()` only triggers for `provider:model` strings. In `oauth_auto` mode a model like `claude-3-5` won't use OAuth, and in `oauth_required` it raises "model has no provider prefix" even when Anthropic is the implicit default. (`llm_do/runtime/agent_runner.py`, `llm_do/oauth/__init__.py`)

### Open Questions
- Should OAuth inference treat bare Anthropic model names as `anthropic:<model>` for oauth_auto/required?
- Should `LLM_DO_MODEL` be normalized (strip + empty -> None) at the config boundary?

### Conclusion
OAuth support is functional but still assumes explicit provider prefixes; env-model normalization is the main ergonomics footgun.
