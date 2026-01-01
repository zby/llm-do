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
