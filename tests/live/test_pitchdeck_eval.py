"""Live tests for the pitchdeck_eval example.

Tests attachment handling, vision capabilities, and worker delegation.

Run:
    pytest tests/live/test_pitchdeck_eval.py -v

Note: Requires a model with PDF/vision support (e.g., Claude, GPT-4 Turbo).
"""

import asyncio
from pathlib import Path

import pytest

from llm_do import run_worker_async

from .conftest import skip_no_anthropic


@skip_no_anthropic
def test_pitchdeck_orchestrator_processes_pdfs(pitchdeck_eval_registry, approve_all_controller):
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
    evaluations_dir.mkdir(exist_ok=True)

    result = asyncio.run(
        run_worker_async(
            registry=pitchdeck_eval_registry,
            worker="main",
            input_data={},
            cli_model="anthropic:claude-haiku-4-5",
            approval_controller=approve_all_controller,
        )
    )

    assert result is not None

    # Check that evaluation files were written
    written_files = list(evaluations_dir.glob("*.md"))
    assert len(written_files) > 0, "Orchestrator should have written at least one evaluation"

    # Check that the evaluation has substantial content
    eval_content = written_files[0].read_text()
    assert len(eval_content) > 200, "Evaluation should have substantial content"


@skip_no_anthropic
def test_pitch_evaluator_directly(pitchdeck_eval_registry, approve_all_controller):
    """Test calling the pitch_evaluator worker directly with an attachment.

    This tests the attachment handling without the orchestrator.
    """
    # Check for PDF files
    input_dir = Path("input")
    pdf_files = list(input_dir.glob("*.pdf")) if input_dir.exists() else []

    if not pdf_files:
        pytest.skip("No PDF files in input/ directory")

    pdf_path = pdf_files[0]

    result = asyncio.run(
        run_worker_async(
            registry=pitchdeck_eval_registry,
            worker="pitch_evaluator",
            input_data="Evaluate this pitch deck.",
            attachments=[str(pdf_path)],
            cli_model="anthropic:claude-haiku-4-5",
            approval_controller=approve_all_controller,
        )
    )

    assert result is not None
    assert result.output is not None
    # Should be a markdown evaluation
    assert len(result.output) > 200, "Evaluation should have substantial content"
