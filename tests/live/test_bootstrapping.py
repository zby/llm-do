"""Live tests for the bootstrapping example.

Tests dynamic agent creation and invocation at runtime.

Run:
    pytest tests/live/test_bootstrapping.py -v

Note: Requires a model with PDF/vision support (e.g., Claude, GPT-4 Turbo).
"""

import asyncio
from pathlib import Path

import pytest

from .conftest import run_example, skip_no_anthropic


@skip_no_anthropic
def test_bootstrapping_creates_dynamic_agent(bootstrapping_example, approve_all_callback):
    """Test that the orchestrator can dynamically create and use agents.

    This is the main integration test for the bootstrapping example.
    It tests:
    - File listing (finding PDFs in input/)
    - Dynamic agent creation (agent_create)
    - Dynamic agent invocation (agent_call)
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
            bootstrapping_example,
            "Process the pitch decks in input/ and write evaluations.",
            model="anthropic:claude-haiku-4-5",
            approval_callback=approve_all_callback,
            generated_agents_dir=bootstrapping_example / "generated",
        )
    )

    assert result is not None

    # Check that evaluation files were written
    written_files = list(evaluations_dir.glob("*.md"))
    assert len(written_files) > 0, "Orchestrator should have written at least one evaluation"

    # Check that the dynamic agent was generated for this session
    generated_agent = Path("generated") / "pitch_evaluator.agent"
    assert generated_agent.exists(), "Dynamic agent should be written to generated/"
