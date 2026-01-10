# Pitch Deck Evaluation (Code Entry Point)

This example demonstrates the **code entry point** pattern using `runtime` where Python code serves as the entry point instead of an LLM orchestrator.

## The Pattern

```
tools.py::main() (deterministic code)
    ├── calls list_pitchdecks() directly
    ├── for each deck: ctx.deps.call("pitch_evaluator", ...)
    └── writes results directly (Path.write_text)

pitch_evaluator.worker (LLM analysis)
```

Compare to the LLM-orchestrated version (`examples/pitchdeck_eval/`):

```
main.worker (LLM orchestrator)
    ├── calls list_files() tool
    ├── for each deck: calls pitch_evaluator worker
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

The `main` tool in `tools.py` uses `RunContext[WorkerRuntime]` to receive
a context object that enables calling other tools:

```python
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import WorkerRuntime

tools = FunctionToolset()

@tools.tool
async def main(ctx: RunContext[WorkerRuntime], input: str) -> str:
    """Entry point - Python orchestration."""
    decks = list_pitchdecks()

    for deck in decks:
        # Call LLM worker for analysis via ctx.deps
        report = await ctx.deps.call(
            "pitch_evaluator",
            {"input": "Evaluate this pitch deck.", "attachments": [deck["file"]]}
        )

        # Write result (deterministic)
        Path(deck["output_path"]).write_text(report)

    return f"Evaluated {len(decks)} pitch deck(s)"
```

Key difference from the old `llm-do` runtime:
- Old: `@tool_context` decorator injects `ctx`
- New: Tool receives `RunContext[WorkerRuntime]` where `ctx.deps` is the WorkerRuntime

The `ctx.deps.call()` method can invoke:
- **Code tools**: Other functions in `FunctionToolset`
- **Worker tools**: `.worker` files (LLM agents)

## Prerequisites

```bash
pip install -e .              # llm-do from repo root (includes python-slugify)
export ANTHROPIC_API_KEY=...
```

## Run

```bash
cd examples/pitchdeck_eval_code_entry
llm-do tools.py pitch_evaluator.worker --entry main --approve-all "Go"
```

Or with a different model:
```bash
llm-do tools.py pitch_evaluator.worker --entry main -m openai:gpt-4o-mini --approve-all "Go"
```

## Files

```
pitchdeck_eval_code_entry/
├── tools.py               # Code entry point: main() + list_pitchdecks()
├── pitch_evaluator.worker # LLM evaluator
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
