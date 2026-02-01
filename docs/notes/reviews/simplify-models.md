# Simplify: models.py

## Context
Review of `llm_do/models.py` for simplification opportunities in model
selection/compatibility helpers.

## Findings
- `get_env_model()` exists but `select_model()` reads `os.environ` directly.
  Use `get_env_model()` inside `select_model()` (or drop the helper) to remove
  duplicated env access and keep tests focused on one path.
- Pattern normalization is repeated per check: `model_matches_pattern()`
  lowercases/strips both model and pattern every time. Consider normalizing
  `compatible_models` once (e.g., `lower().strip()`) so validation is a simple
  membership check on normalized values.
- `resolve_model()` and `get_model_string()` both parse provider prefixes.
  A shared helper could reduce drift if provider parsing rules evolve.

## Open Questions
- Should `select_model()` accept both `agent_model` and `compatible_models`
  (validating compatibility) instead of rejecting the combination?
