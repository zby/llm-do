# Simplify: models.py

## Context
Review of `llm_do/models.py` for simplification opportunities in model
selection/compatibility helpers.

## Findings
- `select_model()` is now a thin wrapper over `select_model_with_id()`. If both
  are always needed, consider returning a `ModelSelection` everywhere and
  letting callers opt into `.model` to reduce parallel APIs.
- Pattern normalization is repeated per check: `model_matches_pattern()`
  lowercases/strips both model and pattern every time. Consider normalizing
  `compatible_models` once (e.g., `lower().strip()`) so validation is a simple
  membership check on normalized values.
- `_resolve_model_string()` and `get_model_string()` both parse provider
  prefixes. A shared helper could reduce drift if provider parsing rules
  evolve.

## Open Questions
- Should `select_model_with_id()` accept both `agent_model` and
  `compatible_models` (validating compatibility) instead of rejecting the
  combination?
