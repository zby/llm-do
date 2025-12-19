"""Live integration tests that make real API calls.

These tests are not run by default. To run them:
    pytest tests/test_integration_live.py -v

Or to run specific tests:
    pytest -k test_nested_worker_with_real_api -v

Requirements:
- ANTHROPIC_API_KEY environment variable must be set
- Will make actual API calls (costs money)
"""
import shutil
from pathlib import Path

import pytest

from llm_do import (
    ApprovalController,
    WorkerRegistry,
    run_worker,
)


pytestmark = pytest.mark.live


@pytest.fixture
def whiteboard_registry(tmp_path, monkeypatch):
    """Registry for the whiteboard_planner example."""
    source = Path(__file__).parent.parent / "examples" / "whiteboard_planner"
    dest = tmp_path / "whiteboard_planner"
    shutil.copytree(source, dest)

    # Change CWD to example directory so relative sandbox paths resolve correctly
    monkeypatch.chdir(dest)
    return WorkerRegistry(dest)


def test_nested_worker_with_real_api(whiteboard_registry):
    """Integration test: nested worker calls with real API now work!

    This test was previously marked as hanging, but the async refactor fixed it.
    It validates that nested worker calls with attachments work end-to-end with
    real API calls.

    Requirements:
    1. Set ANTHROPIC_API_KEY environment variable
    2. Run: pytest tests/test_integration_live.py -v

    What it tests:
    - Orchestrator calls Claude API
    - Orchestrator uses _agent_whiteboard_planner tool to delegate to whiteboard_planner
    - Nested worker receives attachment and calls Claude API again
    - No hang occurs due to async implementation
    - Result is properly returned and written

    Note: This test can be flaky due to non-deterministic LLM behavior.
    If it fails, try running it again or running the example manually:
        cd examples/whiteboard_planner
        llm-do whiteboard_orchestrator --model anthropic:claude-haiku-4-5 --approve-all
    """
    # Verify we're in the temp directory (fixture uses monkeypatch.chdir)
    import os
    cwd = Path(os.getcwd())
    assert "pytest" in str(cwd), f"Test should run in temp dir, got: {cwd}"

    # The example already has input/white_board_plan.png from the copytree
    # Just ensure the plans directory exists in our temp copy
    plans_dir = Path("plans")
    plans_dir.mkdir(exist_ok=True)

    # This will now complete successfully (no hang!)
    result = run_worker(
        registry=whiteboard_registry,
        worker="whiteboard_orchestrator",
        input_data={},
        cli_model="anthropic:claude-haiku-4-5",
        approval_controller=ApprovalController(mode="approve_all"),
    )

    # Verify it completed
    assert result is not None

    # Verify a plan was written (orchestrator's job is to process images and create plans)
    written_files = list(plans_dir.glob("*.md"))
    assert len(written_files) > 0, "Orchestrator should have written at least one plan file"

    # Verify the plan has reasonable content
    plan_content = written_files[0].read_text()
    assert len(plan_content) > 100, "Plan should have substantial content"
