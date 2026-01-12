"""Live tests for the pitchdeck_eval example.

Tests attachment handling, vision capabilities, and worker delegation.

Run:
    pytest tests/live/test_pitchdeck_eval.py -v

Note: Requires a model with PDF/vision support (e.g., Claude, GPT-4 Turbo).
"""

import asyncio
from pathlib import Path

import pytest

from llm_do.runtime import RunApprovalPolicy, Runtime, WorkerInput
from llm_do.runtime.registry import build_entry_registry

from .conftest import run_example, skip_no_anthropic


@skip_no_anthropic
def test_pitchdeck_orchestrator_processes_pdfs(pitchdeck_eval_example, approve_all_callback):
    """Test that the main orchestrator can process PDF pitch decks.

    This is the main integration test for the pitchdeck_eval example.
    It tests:
    - File listing (finding PDFs in input/)
    - Worker delegation (calling pitch_evaluator)
    - Attachment passing (PDF files)
    - Vision/PDF reading capabilities
    - File writing (saving reports)
    """
    # The example should have at least one PDF in input/
    input_dir = Path("input")
    pdf_files = list(input_dir.glob("*.pdf")) if input_dir.exists() else []

    if not pdf_files:
        pytest.skip("No PDF files in input/ directory")

    evaluations_dir = Path("evaluations")
    # Clean output directory to ensure we detect newly written files
    if evaluations_dir.exists():
        for f in evaluations_dir.glob("*.md"):
            f.unlink()
    evaluations_dir.mkdir(exist_ok=True)

    result = asyncio.run(
        run_example(
            pitchdeck_eval_example,
            WorkerInput(input="Process the pitch decks in input/ and write evaluations."),
            model="anthropic:claude-haiku-4-5",
            approval_callback=approve_all_callback,
        )
    )

    assert result is not None

    # Check that evaluation files were written
    written_files = list(evaluations_dir.glob("*.md"))
    assert len(written_files) > 0, "Orchestrator should have written at least one evaluation"


@skip_no_anthropic
def test_pitch_evaluator_directly(pitchdeck_eval_example, approve_all_callback):
    """Test calling the pitch_evaluator worker directly with an attachment.

    This tests the attachment handling without the orchestrator.
    """
    # Check for PDF files
    input_dir = Path("input")
    pdf_files = list(input_dir.glob("*.pdf")) if input_dir.exists() else []

    if not pdf_files:
        pytest.skip("No PDF files in input/ directory")

    pdf_path = pdf_files[0]

    registry = build_entry_registry(
        sorted(str(path) for path in pitchdeck_eval_example.glob("*.worker")),
        sorted(str(path) for path in pitchdeck_eval_example.glob("tools.py")),
        entry_model_override="anthropic:claude-haiku-4-5",
    )
    entry = registry.get("pitch_evaluator")

    runtime = Runtime(
        cli_model="anthropic:claude-haiku-4-5",
        run_approval_policy=RunApprovalPolicy(
            mode="prompt",
            approval_callback=approve_all_callback,
        ),
    )

    result = asyncio.run(
        runtime.run_invocable(
            entry,
            WorkerInput(
                input="Evaluate this pitch deck.",
                attachments=[str(pdf_path)],
            ),
            model="anthropic:claude-haiku-4-5",
        )
    )

    assert result is not None
