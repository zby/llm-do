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

from llm_do.runtime import RunApprovalPolicy, Runtime, Worker
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

HERE = Path(__file__).parent
INPUT_DIR = HERE / "input"
OUTPUT_DIR = HERE / "evaluations"

# =============================================================================
# Worker (global - Workers are reusable across runs)
# =============================================================================

PITCH_EVALUATOR = Worker(
    name="pitch_evaluator",
    model=MODEL,
    instructions=(HERE / "instructions" / "pitch_evaluator.md").read_text(),
    toolsets=[],
    base_path=HERE,  # For resolving attachment paths
)

# =============================================================================
# File discovery
# =============================================================================


def list_pitchdecks() -> list[dict]:
    """List pitch deck PDFs with pre-computed slugs and output paths.

    Returns:
        List of dicts with keys:
        - file: Absolute path to the PDF file
        - slug: URL-safe slug derived from filename
        - output_path: Absolute path for the evaluation report
    """
    result = []
    if INPUT_DIR.exists():
        for pdf in sorted(INPUT_DIR.glob("*.pdf")):
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


def run_evaluation() -> list[str]:
    """Run the pitch deck evaluation workflow."""
    decks = list_pitchdecks()

    if not decks:
        print("No pitch decks found in input directory.")
        return []

    # Set up display backend for progress output
    backend = HeadlessDisplayBackend(stream=sys.stderr, verbosity=VERBOSITY)

    runtime = Runtime(
        cli_model=MODEL,
        run_approval_policy=APPROVAL_POLICY,
        on_event=backend.display if VERBOSITY > 0 else None,
        verbosity=VERBOSITY,
    )

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for i, deck in enumerate(decks, 1):
        print(f"\n[{i}/{len(decks)}] Evaluating: {deck['slug']}", file=sys.stderr)

        result, _ctx = runtime.run(PITCH_EVALUATOR, {
            "input": "Evaluate this pitch deck.",
            "attachments": [deck["file"]],
        })

        # Write result
        output_path = Path(deck["output_path"])
        output_path.write_text(result)
        results.append(deck["slug"])

        print(f"  -> Written to: {output_path.name}", file=sys.stderr)

    return results


def main():
    """Main entry point."""
    print(f"Running with MODEL={MODEL}, APPROVAL_MODE={APPROVAL_POLICY.mode}, VERBOSITY={VERBOSITY}")
    print(f"Input directory: {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("-" * 60)

    results = run_evaluation()

    print("-" * 60)
    if results:
        print(f"Evaluated {len(results)} pitch deck(s): {', '.join(results)}")
    else:
        print("No pitch decks were evaluated.")


if __name__ == "__main__":
    main()
