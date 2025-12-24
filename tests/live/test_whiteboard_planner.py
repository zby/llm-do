"""Live tests for the whiteboard_planner example.

Tests vision capabilities and nested worker delegation with attachments.

Run:
    pytest tests/live/test_whiteboard_planner.py -v

Note: Requires a model with vision capabilities (e.g., Claude, GPT-4 Vision).
"""

import asyncio
from pathlib import Path

import pytest

from llm_do import run_worker_async

from .conftest import skip_no_anthropic


@skip_no_anthropic
def test_whiteboard_orchestrator_processes_images(
    whiteboard_planner_registry, approve_all_controller
):
    """Test that the orchestrator processes whiteboard images.

    This test validates:
    - Orchestrator calls Claude API
    - Orchestrator delegates to whiteboard_planner
    - Nested worker receives attachment and calls API again
    - No hang occurs due to async implementation
    - Result is properly returned and written
    """
    # Ensure plans directory exists
    plans_dir = Path("plans")
    plans_dir.mkdir(exist_ok=True)

    # The example should have input images
    input_dir = Path("input")
    image_files = []
    if input_dir.exists():
        image_files = list(input_dir.glob("*.png")) + list(input_dir.glob("*.jpg"))

    if not image_files:
        pytest.skip("No image files in input/ directory")

    result = asyncio.run(
        run_worker_async(
            registry=whiteboard_planner_registry,
            worker="main",
            input_data={},
            cli_model="anthropic:claude-haiku-4-5",
            approval_controller=approve_all_controller,
        )
    )

    # Verify it completed
    assert result is not None

    # Verify a plan was written
    written_files = list(plans_dir.glob("*.md"))
    assert len(written_files) > 0, "Orchestrator should have written at least one plan file"


@skip_no_anthropic
def test_whiteboard_planner_directly(whiteboard_planner_registry, approve_all_controller):
    """Test calling the whiteboard_planner worker directly with an image.

    This tests the vision capabilities without the orchestrator layer.
    """
    input_dir = Path("input")
    image_files = []
    if input_dir.exists():
        image_files = list(input_dir.glob("*.png")) + list(input_dir.glob("*.jpg"))

    if not image_files:
        pytest.skip("No image files in input/ directory")

    image_path = image_files[0]

    result = asyncio.run(
        run_worker_async(
            registry=whiteboard_planner_registry,
            worker="whiteboard_planner",
            input_data="Analyze this whiteboard and create a plan.",
            attachments=[str(image_path)],
            cli_model="anthropic:claude-haiku-4-5",
            approval_controller=approve_all_controller,
        )
    )

    assert result and result.output is not None
