# Model Compatibility Exception-Only Validation

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Make model compatibility validation raise on mismatch (no result object), and update call sites and tests accordingly.

## Context
- Relevant files/symbols:
  - `llm_do/models.py` (ModelValidationResult, validate_model_compatibility, _validate_and_return, select_model)
  - `tests/test_model_compat.py`
- Related notes (inline summary):
  - Pattern 1: Replace ModelValidationResult with exception-based validation.
    - Behavior: compatible_models None => allow, [] => InvalidCompatibleModelsError, no match => ModelCompatibilityError.
    - Caller should simply call validate_model_compatibility (no return) and rely on exceptions.
  - Pattern 2: Add a ModelError base class for model exceptions.
  - Pattern 8: Inline duplicate normalize helpers in model_matches_pattern.
- How to verify / reproduce:
  - `uv run pytest tests/test_model_compat.py`

## Decision Record
- Decision: incompatibility is exceptional; switch to exception-only validation.
- Inputs: user direction, current flow always uses a single chosen model.
- Options: keep result object vs raise on mismatch.
- Outcome: raise ModelCompatibilityError on mismatch and remove result object.
- Follow-ups: none.

## Tasks
- [ ] Remove ModelValidationResult and any references.
- [ ] Change validate_model_compatibility signature to accept `str | Model`, return None, and raise ModelCompatibilityError on mismatch.
- [ ] Add ModelError base class and update model exceptions to inherit from it.
- [ ] Inline normalization in model_matches_pattern and remove unused helpers.
- [ ] Simplify _validate_and_return to call validate_model_compatibility and return model.
- [ ] Update tests to use `pytest.raises(ModelCompatibilityError)` for mismatches and remove `.valid` checks.

## Current State
Not started.

## Notes
- Keep error messages stable where tests assert on strings.
- Empty compatible_models list should still raise InvalidCompatibleModelsError.
