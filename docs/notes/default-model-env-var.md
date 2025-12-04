# Default Model Environment Variable

**Status**: Design consideration (not implemented)

## Problem

Users must specify `--model` on every invocation if the worker doesn't have a model set:

```bash
llm-do ./my-project "hello" --model anthropic:claude-haiku-4-5
```

An environment variable default would reduce friction:

```bash
export LLM_DO_MODEL=anthropic:claude-haiku-4-5
llm-do ./my-project "hello"
```

## Complication: compatible_models

Workers can declare `compatible_models` to restrict which models work:

```yaml
# Requires Anthropic for native PDF reading
compatible_models:
  - "anthropic:*"
```

If the env var default doesn't match, we have a conflict:

```bash
export LLM_DO_MODEL=openai:gpt-4o-mini
llm-do ./pitchdeck_eval "analyze"
# Error: Model 'openai:gpt-4o-mini' not compatible with 'anthropic:*'
```

## Options

### 1. Strict (same as --model)

Env var checked against `compatible_models`, error if mismatch.

- Pro: Explicit, consistent behavior
- Con: Users must use `--model` for restricted workers

### 2. Env var as weak default

Only use env var if no `compatible_models` specified. Workers with restrictions require explicit `--model`.

- Pro: Restricted workers clearly need explicit model
- Con: Silent behavior difference based on worker config

### 3. Fallback to first compatible

If env var doesn't match `compatible_models`, silently use first pattern from the list.

- Pro: Convenient, "just works"
- Con: Implicit, might use unexpected model

### 4. Warn and require explicit (recommended)

If env var doesn't match, warn and require `--model`:

```
Warning: Default model 'openai:gpt-4o-mini' not compatible with worker.
Compatible: anthropic:*
Use --model to specify explicitly.
```

- Pro: Explicit, informative, surfaces restrictions clearly
- Con: Extra step for restricted workers

## Model Resolution Chain (with env var)

1. Worker's `model` field (if set)
2. Caller's model (during delegation)
3. CLI `--model` flag
4. **Environment variable** (new)
5. Error if none

## Open Questions

- What should the env var be named? `LLM_DO_MODEL`? `LLM_MODEL`?
- Should there be per-provider env vars? `LLM_DO_ANTHROPIC_MODEL`, `LLM_DO_OPENAI_MODEL`?
- Should project.yaml be able to set a project-wide default that takes precedence over env var?
