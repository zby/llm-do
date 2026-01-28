# Pitch Deck Evaluator

Multi-agent example that evaluates startup pitch decks from PDF files.

## Running

```bash
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"
llm-do examples/pitchdeck_eval
```

Place PDF files in `examples/pitchdeck_eval/input/` before running. Reports are written to `evaluations/`.

## What It Does

1. **Orchestrator** (`main.agent`) lists PDFs in the input directory
2. For each PDF, calls the **evaluator** (`pitch_evaluator.agent`)
3. Evaluator analyzes the deck using vision capabilities and returns a markdown report
4. Orchestrator writes reports to the evaluations directory

## Evaluation Criteria

- Problem + urgency (1-5)
- Solution + differentiation (1-5)
- Team strength (1-5)
- Market + traction (1-5)
- Financial clarity (1-5)
- Red flags and verdict (GO / WATCH / PASS)

## Project Structure

```
pitchdeck_eval/
├── main.agent              # Orchestrator
├── pitch_evaluator.agent   # PDF analyzer (vision-capable)
├── project.json
├── input/                  # Place PDFs here
└── evaluations/            # Reports written here
```

## Key Concepts

- **Multi-agent delegation**: Orchestrator delegates to specialized evaluator
- **Vision capabilities**: Evaluator reads PDFs natively via attachments
- **compatible_models**: Evaluator requires a vision-capable model

## Related Examples

- `pitchdeck_eval_stabilized/` - Same workflow with extracted Python tools
- `pitchdeck_eval_code_entry/` - Python orchestration instead of agent orchestration
- `pitchdeck_eval_direct/` - Direct Python scripts without manifest
