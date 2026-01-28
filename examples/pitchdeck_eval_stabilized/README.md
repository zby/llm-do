# Pitch Deck Evaluation (Stabilized Tools)

Demonstrates progressive stabilization: agent orchestration with extracted Python tools.

## Running

```bash
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"
llm-do examples/pitchdeck_eval_stabilized
```

Place PDF files in `examples/pitchdeck_eval_stabilized/input/` before running.

## What It Does

Same as `pitchdeck_eval`, but moves deterministic steps into Python tools:
- `list_pitchdecks()` - File discovery + slug generation (was LLM logic)
- Orchestration remains in the agent

## Path Resolution

`list_pitchdecks()` resolves paths relative to the example directory (project
root), so you can run the manifest from any working directory. Output files
are written to `evaluations/` under the example directory.

## Key Concepts

- **Stabilization**: Move reliable operations from LLM to Python
- **Hybrid approach**: Agent still orchestrates, but delegates mechanical work
