"""Live tests for the whiteboard_planner example.

Tests vision capabilities and nested worker delegation with attachments.

Run:
    pytest tests/live/test_whiteboard_planner.py -v

Note: Requires a model with vision capabilities (e.g., Claude, GPT-4 Vision).
"""

import asyncio
from pathlib import Path

import pytest

from llm_do.runtime import RunApprovalPolicy, Runtime, WorkerInput

from .conftest import build_direct_entry_for_worker, run_example, skip_no_anthropic


@skip_no_anthropic
def test_whiteboard_orchestrator_processes_images(
    whiteboard_planner_example, approve_all_callback
):
    """Test that the orchestrator processes whiteboard images.

    This test validates:
    - Orchestrator calls Claude API
    - Orchestrator delegates to whiteboard_planner
    - Nested worker receives attachment and calls API again
    - No hang occurs due to async implementation
    - Result is properly returned and written
    """
    # Clean output directory to ensure we detect newly written files
    plans_dir = Path("plans")
    if plans_dir.exists():
        for f in plans_dir.glob("*.md"):
            f.unlink()
    plans_dir.mkdir(exist_ok=True)

    # The example should have input images
    input_dir = Path("input")
    image_files = []
    if input_dir.exists():
        image_files = list(input_dir.glob("*.png")) + list(input_dir.glob("*.jpg"))

    if not image_files:
        pytest.skip("No image files in input/ directory")

    result = asyncio.run(
        run_example(
            whiteboard_planner_example,
            WorkerInput(input=""),
            model="anthropic:claude-haiku-4-5",
            approval_callback=approve_all_callback,
        )
    )

    # Verify it completed
    assert result is not None

    # Verify a plan was written
    written_files = list(plans_dir.glob("*.md"))
    assert len(written_files) > 0, "Orchestrator should have written at least one plan file"


@skip_no_anthropic
def test_whiteboard_planner_directly(
    whiteboard_planner_example,
    approve_all_callback,
    tmp_path,
):
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

    entry = build_direct_entry_for_worker(
        whiteboard_planner_example / "whiteboard_planner.worker",
        tmp_path,
        model="anthropic:claude-haiku-4-5",
    )

    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(
            mode="prompt",
            approval_callback=approve_all_callback,
        ),
        project_root=whiteboard_planner_example,
    )

    result = asyncio.run(
        runtime.run_entry(
            entry,
            WorkerInput(
                input="Analyze this whiteboard and create a plan.",
                attachments=[str(image_path)],
            ),
        )
    )

    assert result is not None
