#!/usr/bin/env python
"""Pitch deck evaluation - run directly with Python (no llm-do CLI).

Run with:
    uv run examples/pitchdeck_eval_direct/run.py
    python examples/pitchdeck_eval_direct/run.py

This script demonstrates running llm-do workers directly from Python,
with Python handling the orchestration loop while the LLM handles analysis.
"""

import sys
from pathlib import Path

try:
    from slugify import slugify
except ImportError:
    raise ImportError(
        "python-slugify required. Install with: pip install python-slugify"
    )

from llm_do.runtime import (
    RunApprovalPolicy,
    Runtime,
    Worker,
    WorkerArgs,
    WorkerInput,
    WorkerRuntime,
    entry,
)
from llm_do.ui.display import HeadlessDisplayBackend

# =============================================================================
# CONFIGURATION - Edit these constants to experiment
# =============================================================================

# Model selection
MODEL = "anthropic:claude-haiku-4-5"
# MODEL = "openai:gpt-4o-mini"
# MODEL = "anthropic:claude-sonnet-4-20250514"

# Approval settings
APPROVAL_POLICY = RunApprovalPolicy(
    mode="approve_all",  # For headless safety, use "reject_all" to deny tool approvals.
)

# Verbosity: 0=quiet, 1=show tool calls, 2=stream responses
VERBOSITY = 1

# =============================================================================
# Paths
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.resolve()
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "evaluations"

# =============================================================================
# Worker (global - Workers are reusable across runs)
# =============================================================================

PITCH_EVALUATOR = Worker(
    name="pitch_evaluator",
    model=MODEL,
    instructions=(PROJECT_ROOT / "instructions" / "pitch_evaluator.md").read_text(),
    toolsets=[],
    base_path=PROJECT_ROOT,  # For resolving attachment paths
)

# =============================================================================
# File discovery
# =============================================================================


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
                "output_path": str((OUTPUT_DIR / f"{slug}.md").resolve()),
            })
    return result


# =============================================================================
# Runtime
# =============================================================================


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


def run_evaluation() -> str:
    """Run the pitch deck evaluation workflow."""
    # Set up display backend for progress output
    backend = HeadlessDisplayBackend(stream=sys.stderr, verbosity=VERBOSITY)

    runtime = Runtime(
        cli_model=MODEL,
        run_approval_policy=APPROVAL_POLICY,
        on_event=backend.display if VERBOSITY > 0 else None,
        verbosity=VERBOSITY,
    )

    main.resolve_toolsets({"pitch_evaluator": PITCH_EVALUATOR.as_toolset()})
    result, _ctx = runtime.run(main, {})
    return result


def cli_main():
    """Main entry point."""
    print(f"Running with MODEL={MODEL}, APPROVAL_MODE={APPROVAL_POLICY.mode}, VERBOSITY={VERBOSITY}")
    print(f"Input directory: {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("-" * 60)

    result = run_evaluation()

    print("-" * 60)
    print(result)


if __name__ == "__main__":
    cli_main()
