# Pitch Deck Evaluation (Code Entry Point)

This example demonstrates the **tool-entry-point** pattern where Python code
serves as the entry point instead of an LLM orchestrator.

## The Pattern

```
tools.py::main() (deterministic code)
    ├── calls list_pitchdecks() directly
    ├── for each deck: ctx.call_tool("pitch_evaluator", ...)
    └── writes results directly (Path.write_text)

pitch_evaluator.worker (LLM analysis - unchanged)
```

Compare to the LLM-orchestrated version (`pitchdeck_eval_hardened`):

```
main.worker (LLM orchestrator)
    ├── calls list_pitchdecks() tool
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

The `main()` function in `tools.py` uses the `@tool_context` decorator to
receive a context object that enables calling other tools:

```python
from llm_do import tool_context

@tool_context
async def main(ctx, input: str) -> str:
    """Entry point - Python orchestration."""
    decks = list_pitchdecks()

    for deck in decks:
        # Call LLM worker for analysis
        report = await ctx.call_tool(
            "pitch_evaluator",
            {"input": "Evaluate this pitch deck.", "attachments": [deck["file"]]}
        )

        # Write result (deterministic)
        Path(deck["output_path"]).write_text(report)

    return f"Evaluated {len(decks)} pitch deck(s)"
```

The `ctx.call_tool()` method can invoke:
- **Code tools**: Functions in `tools.py`
- **Worker tools**: `.worker` files (LLM agents)

When calling a worker with attachments, pass a dict with `input` and `attachments`:
```python
await ctx.call_tool("worker_name", {"input": "...", "attachments": ["path.pdf"]})
```

## Prerequisites

```bash
pip install -e .              # llm-do from repo root (includes python-slugify)
export ANTHROPIC_API_KEY=...
```

## Run

```bash
cd examples/pitchdeck_eval_code_entry
llm-do --model anthropic:claude-haiku-4-5 --approve-all
```

Or with a different model:
```bash
llm-do --model openai:gpt-4o-mini --approve-all
```

## Files

```
pitchdeck_eval_code_entry/
├── tools.py              # Code entry point: main() + list_pitchdecks()
├── pitch_evaluator.worker # LLM evaluator (unchanged from hardened)
├── PROCEDURE.md          # Evaluation rubric
├── requirements.txt      # python-slugify>=8.0
├── input/                # Drop PDFs here
└── evaluations/          # Reports written here
```

## The Hardening Spectrum

This example represents "full hardening" - only LLM calls are for actual analysis:

```
Original                 Hardened                 Code Entry Point
─────────────────────────────────────────────────────────────────────
LLM lists files      →   Python tool          →   Python tool
LLM generates slugs  →   Python tool          →   Python tool
LLM orchestrates     →   LLM orchestrates     →   Python code
LLM evaluates        →   LLM evaluates        →   LLM evaluates
```

Choose the right level based on your needs:
- **Original**: Maximum flexibility, highest token cost
- **Hardened**: Mechanical tasks in Python, orchestration in LLM
- **Code Entry Point**: Only reasoning tasks use LLM tokens
