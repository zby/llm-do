"""Test for nested worker call hanging issue.

This test reproduces the bug where calling a worker that uses attachments
from within another worker's tool call causes the system to hang.
"""
import shutil
from pathlib import Path

import pytest

from llm_do import (
    WorkerRegistry,
    approve_all_callback,
    run_worker,
)
from tests.test_examples import ToolCallingModel


pytestmark = pytest.mark.examples


@pytest.fixture
def whiteboard_registry(tmp_path, monkeypatch):
    """Registry for the whiteboard_planner example."""
    source = Path(__file__).parent.parent / "examples" / "whiteboard_planner"
    dest = tmp_path / "whiteboard_planner"
    shutil.copytree(source, dest)

    # Change CWD to example directory so relative sandbox paths resolve correctly
    monkeypatch.chdir(dest)
    return WorkerRegistry(dest)


def test_nested_worker_with_attachments_hang_reproduction(whiteboard_registry):
    """Reproduce the hang when orchestrator calls whiteboard_planner with attachment.

    This test simulates the exact sequence from the live session:
    1. Orchestrator lists files (tries pattern first, then broader search)
    2. Finds white_board_plan.png
    3. Calls whiteboard_planner worker with attachment
    4. Whiteboard_planner should process the image (THIS IS WHERE IT HANGS)

    The hang occurs because:
    - The orchestrator's agent.run_sync creates an event loop
    - worker_call tool runs in an AnyIO worker thread
    - The nested whiteboard_planner agent.run_sync tries to create another event loop
    - Event loop conflict/deadlock occurs
    """
    # Setup input file (whiteboard_registry fixture already changed to example dir)
    input_dir = Path("input")
    input_dir.mkdir(exist_ok=True)
    (input_dir / "white_board_plan.png").write_bytes(b"fake whiteboard image data")

    # Setup plans directory
    plans_dir = Path("plans")
    plans_dir.mkdir(exist_ok=True)

    # Mock the whiteboard_planner's response
    # In reality, this would analyze the image and return markdown
    whiteboard_plan_markdown = """# Project: Whiteboard Planning System

## High-level Summary
This project aims to create an automated system for converting whiteboard photos into structured project plans.

## Epics / Workstreams
- **Epic 1**: Image Processing Pipeline
  - Goal: Build a robust pipeline for ingesting and processing whiteboard images
  - Tasks:
    - [P0] Set up image storage and retrieval system
    - [P1] Implement OCR for text extraction
    - [P1] Add image preprocessing (rotation, contrast enhancement)

- **Epic 2**: AI-Powered Plan Generation
  - Goal: Use LLMs to interpret whiteboard content and generate structured plans
  - Tasks:
    - [P0] Integrate with Claude API for image analysis
    - [P0] Design prompt templates for plan generation
    - [P1] Implement validation and formatting

## Timeline
- Week 1-2: Image Processing Pipeline (Epic 1)
- Week 3-4: AI Integration (Epic 2)
- Week 5: Testing and refinement

## Open Questions / Risks
- Image quality requirements - what's the minimum resolution?
- Handling of handwriting vs. printed text
- Cost of API calls at scale
"""

    # Create a ToolCallingModel that simulates the orchestrator's behavior
    # Based on the actual transcript from the live session
    orchestrator_model = ToolCallingModel([
        # First attempt: list with pattern (returns empty)
        {
            "name": "sandbox_list",
            "args": {"sandbox": "input", "pattern": "**/*.{jpg,jpeg,png}"}
        },
        # Second attempt: list without pattern (finds the file)
        {
            "name": "sandbox_list",
            "args": {"sandbox": "input"}
        },
        # Call the whiteboard_planner worker with attachment
        # In the real scenario with live models, THIS IS WHERE THE HANG OCCURS
        # For this test, we'll mock call_worker to avoid the hang
        {
            "name": "worker_call",
            "args": {
                "worker": "whiteboard_planner",
                "input_data": {"original_filename": "white_board_plan.png"},
                "attachments": ["input/white_board_plan.png"]
            }
        },
        # After getting the plan, write it to the plans sandbox
        {
            "name": "sandbox_write_text",
            "args": {
                "sandbox": "plans",
                "path": "white_board_plan.md",
                "content": whiteboard_plan_markdown
            }
        }
    ])

    # Mock call_worker_async to return the expected plan without actually running the nested worker
    # Now that async is working, we mock the async version instead of the sync version
    from llm_do.base import WorkerRunResult

    async def mock_call_worker_async(**kwargs):
        # Verify the worker_call was made with correct parameters
        assert kwargs["worker"] == "whiteboard_planner"
        assert kwargs["input_data"] == {"original_filename": "white_board_plan.png"}
        assert len(kwargs["attachments"]) == 1
        assert "white_board_plan.png" in str(kwargs["attachments"][0].path)

        # Return the mocked plan
        return WorkerRunResult(output=whiteboard_plan_markdown, messages=[])

    import llm_do.base
    original_call_worker_async = llm_do.base.call_worker_async
    llm_do.base.call_worker_async = mock_call_worker_async

    try:
        # Run the orchestrator
        result = run_worker(
            registry=whiteboard_registry,
            worker="whiteboard_orchestrator",
            input_data={},
            cli_model=orchestrator_model,
            approval_callback=approve_all_callback,
        )

        assert result is not None

        # Verify the plan was written
        plans_dir = Path("plans")
        assert (plans_dir / "white_board_plan.md").exists()
        plan_content = (plans_dir / "white_board_plan.md").read_text()
        assert "Project: Whiteboard Planning System" in plan_content
    finally:
        # Restore original call_worker_async
        llm_do.base.call_worker_async = original_call_worker_async


@pytest.mark.skip(reason="TestModel makes default tool calls that fail without sandboxes")
def test_direct_whiteboard_planner_works(whiteboard_registry):
    """Verify that whiteboard_planner works when called directly (not nested).

    This test confirms that the issue is specific to nested worker calls,
    not a problem with the whiteboard_planner worker itself.
    """
    # Setup input file
    input_dir = Path("input")
    input_dir.mkdir(exist_ok=True)
    test_image = input_dir / "test_board.png"
    test_image.write_bytes(b"fake whiteboard image data")

    # Mock the LLM response for whiteboard_planner
    # The whiteboard_planner worker just returns text (markdown), no tools
    from pydantic_ai.models.test import TestModel

    plan_text = """# Project: Test Board

## High-level Summary
A simple test project.

## Epics / Workstreams
- **Epic 1**: Setup
  - Goal: Initialize the project
  - Tasks:
    - [P0] Create repository

## Timeline
- Week 1: Setup

## Open Questions / Risks
- None identified
"""

    planner_model = TestModel()

    # Call whiteboard_planner directly (not through orchestrator)
    result = run_worker(
        registry=whiteboard_registry,
        worker="whiteboard_planner",
        input_data={"original_filename": "test_board.png"},
        attachments=[str(test_image.absolute())],
        cli_model=planner_model,
        approval_callback=approve_all_callback,
    )

    assert result is not None
    # TestModel returns a default response, so we just verify it didn't hang
    assert result.output is not None


@pytest.mark.skip(reason="This test will hang - use to reproduce the bug")
def test_nested_worker_with_real_models_hangs(whiteboard_registry):
    """Test that demonstrates the actual hang with real models.

    WARNING: This test will hang when run with real API models!
    Only run this manually when debugging the issue.

    To reproduce:
    1. Set ANTHROPIC_API_KEY
    2. Run: pytest -k test_nested_worker_with_real_models_hangs -v
    3. Observe the hang at the nested worker_call
    """
    # Setup input file
    input_dir = Path("input")
    input_dir.mkdir(exist_ok=True)
    (input_dir / "white_board_plan.png").write_bytes(b"fake whiteboard image data")

    # This will hang when worker_call tries to invoke whiteboard_planner
    result = run_worker(
        registry=whiteboard_registry,
        worker="whiteboard_orchestrator",
        input_data={},
        cli_model="anthropic:claude-haiku-4-5",
        approval_callback=approve_all_callback,
    )

    # Never reaches here due to hang
    assert result is not None
