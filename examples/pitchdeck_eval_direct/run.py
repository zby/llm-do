#!/usr/bin/env python
"""Pitch deck evaluation with switchable TUI or headless UI.

Run with:
    uv run examples/pitchdeck_eval_direct/run.py
    python examples/pitchdeck_eval_direct/run.py

Set UI_MODE to "tui" or "headless" to switch modes.
"""

import asyncio
import os
import sys
from pathlib import Path

try:
    from slugify import slugify
except ImportError:
    raise ImportError("python-slugify required. Install with: pip install python-slugify")

from llm_do.runtime import AgentSpec, EntrySpec, WorkerRuntime
from llm_do.ui import run_ui

# =============================================================================
# CONFIGURATION - Edit these constants to experiment
# =============================================================================

# Model selection
MODEL = "anthropic:claude-haiku-4-5"
# MODEL = "openai:gpt-4o-mini"
# MODEL = "anthropic:claude-sonnet-4-20250514"

# UI mode: "tui" or "headless"
UI_MODE = os.environ.get("LLM_DO_UI_MODE", "tui")
if UI_MODE not in {"tui", "headless"}:
    raise ValueError("UI_MODE must be 'tui' or 'headless'")

# Approval mode: "prompt" for TUI, "approve_all"/"reject_all" for headless
APPROVAL_MODE = "prompt" if UI_MODE == "tui" else "approve_all"

# Verbosity: 1=show tool calls, 2=stream responses
VERBOSITY = 1

# =============================================================================
# Paths
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.resolve()
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "evaluations"

# =============================================================================
# Agent (global - reusable across runs)
# =============================================================================

PITCH_EVALUATOR = AgentSpec(
    name="pitch_evaluator",
    model=MODEL,
    instructions=(PROJECT_ROOT / "instructions" / "pitch_evaluator.md").read_text(),
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
# Entry point
# =============================================================================


async def main(_input_data, runtime: WorkerRuntime) -> str:
    """Evaluate all pitch decks in input directory.

    This is a code entry point that orchestrates the evaluation workflow:
    1. List all pitch deck PDFs (deterministic)
    2. Call LLM worker for each deck (LLM reasoning)
    3. Write results to files (deterministic)

    File paths are relative to the project root (this file's directory).
    """
    decks = list_pitchdecks()

    if not decks:
        return "No pitch decks found in input directory."

    results = []

    for deck in decks:
        report = await runtime.call_agent(
            PITCH_EVALUATOR,
            {"input": "Evaluate this pitch deck.", "attachments": [deck["file"]]},
        )

        # Write result (deterministic)
        output_path = Path(deck["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        results.append(deck["slug"])

    return f"Evaluated {len(results)} pitch deck(s): {', '.join(results)}"


ENTRY_SPEC = EntrySpec(name="main", main=main)


def cli_main():
    """Main entry point."""
    print(f"Starting {UI_MODE} with MODEL={MODEL}, APPROVAL_MODE={APPROVAL_MODE}")
    print(f"Input directory: {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("-" * 60)

    outcome = asyncio.run(run_ui(
        entry=ENTRY_SPEC,
        input={"input": ""},
        project_root=PROJECT_ROOT,
        approval_mode=APPROVAL_MODE,
        mode=UI_MODE,
        verbosity=VERBOSITY,
        return_permission_errors=True,
    ))
    if outcome.result is not None:
        print(outcome.result)
    sys.exit(outcome.exit_code)


if __name__ == "__main__":
    cli_main()
