"""Pitch deck-style demo for the context-centric runtime experiment."""
from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext, Tool

from tool_calling_model import ToolCallingModel

from ctx import Context
from entries import ToolEntry, WorkerEntry


class PitchEvalInput(BaseModel):
    input: str
    attachments: list[str]


# Standard PydanticAI tool signatures
async def list_files(ctx: RunContext[Context], path: str, pattern: str = "*.pdf") -> list[str]:
    """List files matching a pattern in a directory."""
    base = Path(path)
    return [str(p) for p in sorted(base.glob(pattern))]


async def count_pages(ctx: RunContext[Context], pdf_path: str) -> int:
    """Count pages in a PDF (stub - returns 10)."""
    return 10


async def write_file(ctx: RunContext[Context], path: str, content: str) -> str:
    """Write content to a file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return str(p)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    input_dir = root / "examples" / "pitchdeck_eval" / "input"
    output_dir = root / "experiments" / "context_runtime" / "evaluations"

    evaluation_report = "# Evaluation\n\nStrengths: Clear. Weaknesses: Limited."

    evaluator = WorkerEntry(
        name="pitch_evaluator",
        instructions="Return a markdown evaluation report for the attached PDF. Use count_pages to check length.",
        model=TestModel(
            call_tools=["count_pages"],
            custom_output_text=evaluation_report,
        ),
        tools=[ToolEntry(tool=Tool(count_pages, name="count_pages"))],
        schema_in=PitchEvalInput,
    )

    orchestrator = WorkerEntry(
        name="pitch_orchestrator",
        instructions=(
            "Evaluate each pitch deck PDF in the input directory. Use list_files to find PDFs, "
            "convert each filename to a slug (lowercase, hyphenated), call pitch_evaluator with "
            "the PDF as an attachment, and write the returned markdown to evaluations/{slug}.md."
        ),
        model=ToolCallingModel(
            {
                "tool_calls": [
                    {
                        "name": "list_files",
                        "args": {"path": str(input_dir), "pattern": "*.pdf"},
                    },
                    {
                        "name": "pitch_evaluator",
                        "args": {
                            "input": "Evaluate this pitch deck.",
                            "attachments": [str(input_dir / "acma_pitchdeck.pdf")],
                        },
                    },
                    {
                        "name": "write_file",
                        "args": {
                            "path": str(output_dir / "acma-pitchdeck.md"),
                            "content": evaluation_report,
                        },
                    },
                ]
            }
        ),
        tools=[
            ToolEntry(tool=Tool(list_files, name="list_files")),
            evaluator,
            ToolEntry(tool=Tool(write_file, name="write_file")),
        ],
    )

    ctx = Context.from_worker(orchestrator)

    result = asyncio.run(ctx.call("pitch_orchestrator", "Evaluate pitch decks."))
    print("Result:", result)
    print("Output dir:", output_dir)
    print("Trace:")
    for t in ctx.trace:
        print(f"  {t.name} ({t.kind}) depth={t.depth}")
    print("Usage:", ctx.usage)
