import shutil
from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

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
    source = Path(__file__).parent.parent
    dest = tmp_path / "whiteboard_planner"
    shutil.copytree(source, dest)
    
    # Change CWD to example directory so relative sandbox paths resolve correctly
    monkeypatch.chdir(dest)
    return WorkerRegistry(dest)


def test_whiteboard_planner_loading(whiteboard_registry):
    """Test that whiteboard_planner loads correctly."""
    definition = whiteboard_registry.load_definition("whiteboard_planner")
    assert definition.name == "whiteboard_planner"
    assert definition.attachment_policy is not None
    assert ".jpg" in definition.attachment_policy.allowed_suffixes


def test_whiteboard_orchestrator_loading(whiteboard_registry):
    """Test that whiteboard_orchestrator loads correctly."""
    definition = whiteboard_registry.load_definition("whiteboard_orchestrator")
    assert definition.name == "whiteboard_orchestrator"
    assert "input" in definition.sandboxes
    assert "plans" in definition.sandboxes
    assert "whiteboard_planner" in definition.allow_workers


def test_whiteboard_orchestrator_execution(whiteboard_registry, tmp_path):
    """Test the orchestrator flow with a mock model."""
    # Setup input file
    input_dir = Path("input")
    input_dir.mkdir(exist_ok=True)
    (input_dir / "test_board.jpg").write_bytes(b"fake image data")

    # Mock model that simulates the orchestrator's tool calls
    # 1. List files
    # 2. Call worker
    # 3. Write plan
    
    plan_content = "# Project Plan\n\nTasks..."
    
    model = ToolCallingModel([
        {
            "name": "list_files",
            "args": {"path": "input", "pattern": "*.jpg"}
        },
        {
            "name": "worker_call",
            "args": {
                "worker": "whiteboard_planner",
                "input_data": {"original_filename": "test_board.jpg"},
                "attachments": ["input/test_board.jpg"]
            }
        },
        {
            "name": "write_file",
            "args": {
                "path": "plans/test_board.md",
                "content": plan_content
            }
        }
    ])

    result = run_worker(
        registry=whiteboard_registry,
        worker="whiteboard_orchestrator",
        input_data="Process images",
        cli_model=model,
        approval_callback=approve_all_callback,
    )

    assert result is not None
    
    # Verify file was written
    plans_dir = Path("plans")
    assert (plans_dir / "test_board.md").exists()
    assert (plans_dir / "test_board.md").read_text() == plan_content
