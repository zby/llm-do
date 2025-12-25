# Config and Auth Review

## Context
Review of config and auth modules for bugs, inconsistencies, and overengineering.

## Findings
- `llm_do/config_overrides.py`
  - `apply_overrides` only makes a shallow copy before applying overrides. Nested updates mutate the input dictionary because shared sub-dictionaries are modified in place. This surprises callers that expect `data` to stay unchanged when passing it for transformation.

- `llm_do/model_compat.py`
  - File header claims CLI `--model` has highest precedence, but `select_model` prioritizes `worker_model` first, then CLI, then env. CLI overrides cannot replace a worker-defined model, so the documentation and behavior disagree.
  - `compatible_models` entries are assumed to be strings; non-string patterns will raise unexpected errors via `fnmatch` instead of a clear configuration error. There is no validation of the list contents before matching.

- `llm_do/oauth/`
  - The Anthropic login flow never validates that the returned `state` matches the PKCE verifier. This skips CSRF protection and accepts any pasted code regardless of the state value.
  - OAuth tokens are saved in plaintext to `~/.llm-do/oauth.json` without any user warnings. That may be acceptable for local dev, but it is worth documenting or hardening if intended for broader use.

## Open Questions
- Should `apply_overrides` deep copy nested structures (or document the mutation) so caller data stays immutable?
- Should CLI `--model` be allowed to override a worker’s `model` when needed, or should the doc comment be corrected to match current precedence?
- Do we want to validate `compatible_models` entries eagerly and raise clearer errors for non-string patterns?
- Should the Anthropic OAuth flow enforce state verification (and possibly nonce handling) to close the CSRF gap?
- Is plaintext storage of OAuth tokens acceptable, or should we encrypt or otherwise warn users?

## Conclusion
Open items above remain unresolved.
