"""Code entry point for pitch deck evaluation using runtime.

This example demonstrates the @entry pattern where Python code is the
entry point instead of an LLM orchestrator. The main() function handles
all deterministic orchestration (list files, loop, write results) while
the pitch_evaluator worker handles the actual LLM analysis.

Benefits:
- No token waste on trivial orchestration logic
- Deterministic file handling and output paths
- LLM only used for actual reasoning tasks (evaluation)
- Tool calls still flow through the tool plane (approvals/events) even though
  entry code is trusted

File paths are relative to this file's directory (the project root),
matching the behavior of filesystem_project toolset.
"""

from pathlib import Path

try:
    from slugify import slugify
except ImportError:
    raise ImportError(
        "python-slugify required. Install with: pip install python-slugify"
    )

from llm_do.runtime import WorkerArgs, WorkerInput, WorkerRuntime, entry

# Project root is the directory containing this file
PROJECT_ROOT = Path(__file__).parent.resolve()


def list_pitchdecks(input_dir: str = "input") -> list[dict]:
    """List pitch deck PDFs with pre-computed slugs and output paths.

    Args:
        input_dir: Directory to scan for PDF files, relative to project root.

    Returns:
        List of dicts with keys:
        - file: Absolute path to the PDF file
        - slug: URL-safe slug derived from filename
        - output_path: Absolute path for the evaluation report
    """
    input_path = PROJECT_ROOT / input_dir
    result = []
    if input_path.exists():
        for pdf in sorted(input_path.glob("*.pdf")):
            slug = slugify(pdf.stem)
            result.append({
                "file": str(pdf.resolve()),
                "slug": slug,
                "output_path": str((PROJECT_ROOT / "evaluations" / f"{slug}.md").resolve()),
            })
    return result


@entry(toolsets=["pitch_evaluator"])
async def main(args: WorkerArgs, runtime: WorkerRuntime) -> str:
    """Evaluate all pitch decks in input directory.

    This is a code entry point that orchestrates the evaluation workflow:
    1. List all pitch deck PDFs (deterministic)
    2. Call LLM worker for each deck (LLM reasoning)
    3. Write results to files (deterministic)

    File paths are relative to the project root (this file's directory).

    Args:
        args: WorkerArgs input (ignored - workflow is deterministic)
        runtime: WorkerRuntime for calling workers
    """
    decks = list_pitchdecks()

    if not decks:
        return "No pitch decks found in input directory."

    results = []

    for deck in decks:
        report = await runtime.call(
            "pitch_evaluator",
            WorkerInput(
                input="Evaluate this pitch deck.",
                attachments=[deck["file"]],
            ),
        )

        # Write result (deterministic)
        output_path = Path(deck["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        results.append(deck["slug"])

    return f"Evaluated {len(results)} pitch deck(s): {', '.join(results)}"
