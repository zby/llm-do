"""Code entry point demo - Python tool calling LLM workers.

This example demonstrates the code-entry-point pattern where Python code
is the entry point instead of an LLM orchestrator. The main tool handles
all deterministic orchestration (list files, loop, write results) while
the pitch_evaluator worker handles the actual LLM analysis.

Benefits:
- No token waste on trivial orchestration logic
- Deterministic file handling and output paths
- LLM only used for actual reasoning tasks (evaluation)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic import BaseModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext, Tool

from src.ctx import Context
from src.entries import ToolEntry, WorkerEntry


class PitchEvalInput(BaseModel):
    input: str
    attachments: list[str]


def slugify(text: str) -> str:
    """Simple slug generator."""
    return text.lower().replace("_", "-").replace(" ", "-")


async def evaluate_pitchdecks(ctx: RunContext[Context], input_dir: str) -> str:
    """Code entry point that orchestrates pitch deck evaluation.

    Deterministic orchestration in Python:
    1. List all pitch deck PDFs
    2. Call LLM worker for each deck
    3. Write results to files

    The ctx.deps provides access to the orchestration Context for calling workers.
    """
    # Deterministic: list files
    decks = []
    for pdf in sorted(Path(input_dir).glob("*.pdf")):
        slug = slugify(pdf.stem)
        decks.append({
            "file": str(pdf),
            "slug": slug,
            "output_path": f"evaluations/{slug}.md",
        })

    if not decks:
        return "No pitch decks found."

    results = []
    for deck in decks:
        # Call LLM worker for analysis via ctx.deps
        report = await ctx.deps.call(
            "pitch_evaluator",
            {"input": "Evaluate this pitch deck.", "attachments": [deck["file"]]}
        )

        # Deterministic: write result
        output_path = Path(deck["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(str(report))
        results.append(deck["slug"])

    return f"Evaluated {len(results)} pitch deck(s): {', '.join(results)}"


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    input_dir = root / "examples" / "pitchdeck_eval" / "input"

    evaluation_report = "# Evaluation\n\nStrengths: Clear. Weaknesses: Limited."

    # LLM worker for actual reasoning
    evaluator = WorkerEntry(
        name="pitch_evaluator",
        instructions="Return a markdown evaluation report for the attached PDF.",
        model=TestModel(custom_output_text=evaluation_report),
        schema_in=PitchEvalInput,
    )

    # Code entry point as a tool
    main_tool = ToolEntry(tool=Tool(evaluate_pitchdecks, name="evaluate_pitchdecks"))

    # Create context with the evaluator worker available for the tool to call
    ctx = Context.from_tool_entries(
        [evaluator],
        model=TestModel(custom_output_text="unused"),
    )

    # Run with code as entry point (not LLM orchestrator)
    result = asyncio.run(ctx.run(main_tool, {"input_dir": str(input_dir)}))

    print("Result:", result)
    print("\nTrace:")
    for t in ctx.trace:
        print(f"  {t.name} ({t.kind}) depth={t.depth}")
    print("\nUsage:", ctx.usage)
