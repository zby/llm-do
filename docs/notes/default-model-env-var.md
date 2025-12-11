# Default Model Environment Variable

**Status**: Implemented

## Summary

Model resolution follows this precedence (highest to lowest):

1. CLI `--model` flag (explicit override)
2. Worker's `model` field (from worker definition)
3. Project `model` field (from project.yaml)
4. `LLM_DO_MODEL` environment variable (global default)

All models are validated against worker's `compatible_models` patterns. If the selected model doesn't match any pattern, a `ModelCompatibilityError` is raised.

## Usage

```bash
# Set global default
export LLM_DO_MODEL=anthropic:claude-haiku-4-5

# Run without specifying model - uses env var
llm-do ./my-project "hello"

# Override with CLI flag
llm-do ./my-project "hello" --model openai:gpt-4o

# Project can set default in project.yaml:
# model: anthropic:claude-sonnet-4
```

## compatible_models Validation

All models (from any source) are validated against the worker's `compatible_models` patterns:

```yaml
# Worker definition
compatible_models:
  - "anthropic:*"
```

If `LLM_DO_MODEL=openai:gpt-4o` but the worker requires Anthropic:

```
Error: Model 'openai:gpt-4o' is not compatible with worker 'my-worker'.
Compatible patterns: anthropic:*
```

## Implementation

See `llm_do/model_compat.py`:
- `select_model()` - resolves model with precedence
- `get_env_model()` - reads `LLM_DO_MODEL` env var
- `validate_model_compatibility()` - checks against patterns
