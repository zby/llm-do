"""Code entry point for pitch deck evaluation using ctx_runtime.

This example demonstrates the tool-entry-point pattern where Python code
is the entry point instead of an LLM orchestrator. The main() function
handles all deterministic orchestration (list files, loop, write results)
while the pitch_evaluator worker handles the actual LLM analysis.

Benefits:
- No token waste on trivial orchestration logic
- Deterministic file handling and output paths
- LLM only used for actual reasoning tasks (evaluation)

Key difference from the old llm-do runtime:
- Old: @tool_context decorator injects ctx
- New: Tool receives RunContext[Context] where run_ctx.deps is the Context
"""

from pathlib import Path

from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset

try:
    from slugify import slugify
except ImportError:
    raise ImportError(
        "python-slugify required. Install with: pip install python-slugify"
    )

# Import Context type for type hints
from llm_do.ctx_runtime import Context

tools = FunctionToolset()


def list_pitchdecks(path: str = "input") -> list[dict]:
    """List pitch deck PDFs with pre-computed slugs and output paths.

    Args:
        path: Directory to scan for PDF files. Defaults to "input".

    Returns:
        List of dicts with keys:
        - file: Path to the PDF file
        - slug: URL-safe slug derived from filename
        - output_path: Suggested output path for the evaluation report
    """
    result = []
    for pdf in sorted(Path(path).glob("*.pdf")):
        slug = slugify(pdf.stem)
        result.append({
            "file": str(pdf),
            "slug": slug,
            "output_path": f"evaluations/{slug}.md",
        })
    return result


@tools.tool
async def main(ctx: RunContext[Context], input: str) -> str:
    """Evaluate all pitch decks in input directory.

    This is a code entry point that orchestrates the evaluation workflow:
    1. List all pitch deck PDFs (deterministic)
    2. Call LLM worker for each deck (LLM reasoning)
    3. Write results to files (deterministic)

    The ctx parameter is a RunContext where ctx.deps provides access to
    call() for invoking other tools including LLM workers.

    Args:
        ctx: RunContext with Context as deps - provides call() method
        input: User input (ignored - workflow is deterministic)
    """
    decks = list_pitchdecks()

    if not decks:
        return "No pitch decks found in input directory."

    results = []

    for deck in decks:
        # Call LLM worker for analysis via ctx.deps (the Context)
        report = await ctx.deps.call(
            "pitch_evaluator",
            {"input": "Evaluate this pitch deck.", "attachments": [deck["file"]]}
        )

        # Write result (deterministic)
        output_path = Path(deck["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        results.append(deck["slug"])

    return f"Evaluated {len(results)} pitch deck(s): {', '.join(results)}"
