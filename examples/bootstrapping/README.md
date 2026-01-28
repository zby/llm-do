# Bootstrapping Example

Demonstrates dynamic agent creation at runtime.

## Running

```bash
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"
llm-do examples/bootstrapping
```

Place PDF files in `examples/bootstrapping/input/` before running.

## What It Does

Similar to `pitchdeck_eval`, but instead of using a predefined evaluator agent, the orchestrator **creates the evaluator dynamically** at runtime using `agent_create`.

1. Orchestrator calls `agent_create` to define the pitch evaluator
2. Lists PDFs in the input directory
3. Calls the dynamically created evaluator for each PDF
4. Writes reports to the evaluations directory

## Project Structure

```
bootstrapping/
├── main.agent          # Orchestrator with dynamic_agents toolset
├── project.json
├── input/              # Place PDFs here
└── evaluations/        # Reports written here
```

## Key Concepts

- **Dynamic agents**: Create agents at runtime via `agent_create` tool
- **Runtime flexibility**: Agent definitions can be computed or loaded dynamically
- **Same capabilities**: Dynamic agents work identically to statically defined ones

## Comparison with pitchdeck_eval

| Aspect | pitchdeck_eval | bootstrapping |
|--------|----------------|---------------|
| Evaluator definition | Static `.agent` file | Dynamic via `agent_create` |
| When defined | Build time | Runtime |
| Use case | Known, fixed agents | Flexible, computed agents |
