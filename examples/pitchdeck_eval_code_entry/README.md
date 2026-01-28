# Pitch Deck Evaluation (Code Entry Point)

This example demonstrates the **code entry point** pattern using `runtime` where Python code serves as the entry point instead of an LLM orchestrator.

## The Pattern

```
tools.py::main (deterministic code)
    ├── calls list_pitchdecks() directly
    ├── for each deck: runtime.call_agent("pitch_evaluator", ...)
    └── writes results directly (Path.write_text)

pitch_evaluator.agent (LLM analysis)
```

Compare to the LLM-orchestrated version (`examples/pitchdeck_eval/`):

```
main.agent (LLM orchestrator)
    ├── calls list_files() tool
    ├── for each deck: calls pitch_evaluator agent
    └── writes results via filesystem tool
```

## Why Code Entry Points?

The orchestration logic in this workflow is purely mechanical:
1. List PDF files in a directory
2. Loop over each file
3. Call an analyzer
4. Write results to disk

An LLM adds no value to these steps. Using a code entry point:

- **Saves tokens**: No LLM reasoning for trivial orchestration
- **Deterministic**: Same input always produces same behavior
- **Faster**: No LLM latency for the orchestration loop
- **Testable**: Pure Python functions can be unit tested

The LLM is reserved for what it's good at: **evaluating pitch decks**.

## How It Works

The entry function in `tools.py` is selected by `project.json` and receives a
runtime handle, so it can call agents by name:

```python
from llm_do.runtime import CallContext

async def main(_input_data, runtime: CallContext) -> str:
    """Entry point - Python orchestration."""
    decks = list_pitchdecks()

    for deck in decks:
        # Call LLM agent via call_agent
        report = await runtime.call_agent(
            "pitch_evaluator",
            {"input": "Evaluate this pitch deck.", "attachments": [deck["file"]]},
        )

        # Write result (deterministic)
        Path(deck["output_path"]).write_text(report)

    return f"Evaluated {len(decks)} pitch deck(s)"

```

The `runtime.call_agent()` method accepts either:
- An agent name (string) - looks up the agent in the registry (populated from `.agent` files)
- An `AgentSpec` instance - invokes the agent directly

Entry functions are trusted code, but agent calls still go through the tool
plane and respect approval policies/toolset configs (for parity and
observability). Use `approval_mode: "prompt"` in `project.json` if you want
interactive approvals.

## Prerequisites

```bash
pip install -e .              # llm-do from repo root
export ANTHROPIC_API_KEY=...
```

## Run

```bash
# Run from anywhere - no cd needed
llm-do examples/pitchdeck_eval_code_entry/project.json

# Or with uv
uv run llm-do examples/pitchdeck_eval_code_entry/project.json
```

File paths (`input/`, `evaluations/`) resolve relative to where `tools.py` lives,
matching how `filesystem_project` works for agent files.

To use a different model, edit the `model:` field in `pitch_evaluator.agent` (must support PDF/vision).

## Files

```
pitchdeck_eval_code_entry/
├── project.json           # Manifest defining entry point and files
├── tools.py               # Code entry point: main() + list_pitchdecks()
├── pitch_evaluator.agent # LLM evaluator
├── input/                 # Drop PDFs here
└── evaluations/           # Reports written here
```

## The Stabilizing Spectrum

This example represents "full stabilizing" - only LLM calls are for actual analysis:

```
Original                 LLM-Orchestrated         Code Entry Point
─────────────────────────────────────────────────────────────────────
LLM lists files      →   Python tool          →   Python tool
LLM generates slugs  →   Python tool          →   Python tool
LLM orchestrates     →   LLM orchestrates     →   Python code
LLM evaluates        →   LLM evaluates        →   LLM evaluates
```

Choose the right level based on your needs:
- **LLM-Orchestrated**: Mechanical tasks in Python, orchestration in LLM
- **Code Entry Point**: Only reasoning tasks use LLM tokens

See also `examples/pitchdeck_eval_direct/` for running the same pattern directly from Python without the CLI.
