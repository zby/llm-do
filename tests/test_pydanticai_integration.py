"""Integration tests using mocked LLM models with predefined tool calls."""
import json
from pathlib import Path

import pytest

from llm_do import (
    ApprovalController,
    ApprovalDecision,
    WorkerDefinition,
    WorkerRegistry,
    run_worker,
)
from pydantic_ai_blocking_approval import ApprovalRequest
from llm_do.worker_sandbox import SandboxConfig
from pydantic_ai_filesystem_sandbox import PathConfig


def _project_root(tmp_path):
    root = tmp_path / "project"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def registry(tmp_path):
    return WorkerRegistry(_project_root(tmp_path))


def test_integration_approve_all_allows_write(tmp_path, registry, tool_calling_model_cls):
    """Integration test: worker writes file with --approve-all."""
    sandbox_path = tmp_path / "output"
    path_cfg = PathConfig(
        root=str(sandbox_path),
        mode="rw",
        suffixes=[".txt"],
        write_approval=True,  # Require approval for writes
    )

    definition = WorkerDefinition(
        name="writer",
        instructions="Write a test file",
        sandbox=SandboxConfig(paths={"out": path_cfg}),
        toolsets={"filesystem": {}},
    )
    registry.save_definition(definition)

    # Mock LLM that calls sandbox_write_text
    mock_model = tool_calling_model_cls(
        [
            {
                "name": "write_file",
                "args": {
                    "path": "out/test.txt",
                    "content": "Hello from test!",
                },
            }
        ]
    )

    result = run_worker(
        registry=registry,
        worker="writer",
        input_data="Write a test file",
        cli_model=mock_model,
        approval_controller=ApprovalController(mode="approve_all"),
    )

    # Verify file was written
    assert (sandbox_path / "test.txt").exists()
    assert (sandbox_path / "test.txt").read_text() == "Hello from test!"
    assert result.output == "Task completed"


def test_integration_strict_mode_blocks_write(tmp_path, registry, tool_calling_model_cls):
    """Integration test: worker fails in --strict mode."""
    sandbox_path = tmp_path / "output"
    path_cfg = PathConfig(
        root=str(sandbox_path),
        mode="rw",
        suffixes=[".txt"],
        write_approval=True,  # Require approval for writes
    )

    definition = WorkerDefinition(
        name="writer",
        instructions="Write a test file",
        sandbox=SandboxConfig(paths={"out": path_cfg}),
        toolsets={"filesystem": {}},
    )
    registry.save_definition(definition)

    # Mock LLM that tries to call sandbox_write_text
    mock_model = tool_calling_model_cls(
        [
            {
                "name": "write_file",
                "args": {
                    "path": "out/test.txt",
                    "content": "Hello from test!",
                },
            }
        ]
    )

    with pytest.raises(PermissionError, match="User denied write_file.*Strict mode"):
        run_worker(
            registry=registry,
            worker="writer",
            input_data="Write a test file",
            cli_model=mock_model,
            approval_controller=ApprovalController(mode="strict"),
        )

    # Verify file was NOT written
    assert not (sandbox_path / "test.txt").exists()


def test_integration_multiple_tool_calls_with_session_approval(
    tmp_path, registry, tool_calling_model_cls
):
    """Integration test: multiple tool calls with session approval."""
    sandbox_path = tmp_path / "output"
    path_cfg = PathConfig(
        root=str(sandbox_path),
        mode="rw",
        suffixes=[".txt"],
        write_approval=True,  # Require approval for writes
    )

    definition = WorkerDefinition(
        name="multi-writer",
        instructions="Write multiple files",
        sandbox=SandboxConfig(paths={"out": path_cfg}),
        toolsets={"filesystem": {}},
    )
    registry.save_definition(definition)

    # Mock LLM that makes multiple identical write calls
    # Session approval should work for identical payloads (same args)
    mock_model = tool_calling_model_cls(
        [
            {
                "name": "write_file",
                "args": {"path": "out/test.txt", "content": "same content"},
            },
            {
                "name": "write_file",
                "args": {"path": "out/test.txt", "content": "same content"},
            },
            {
                "name": "write_file",
                "args": {"path": "out/test.txt", "content": "same content"},
            },
        ]
    )

    # Custom callback: approve first call for session
    call_count = 0

    def session_approval_callback(request: ApprovalRequest) -> ApprovalDecision:
        nonlocal call_count
        call_count += 1
        # First call: approve for session (subsequent identical calls auto-approved)
        return ApprovalDecision(approved=True, remember="session")

    session_controller = ApprovalController(mode="interactive", approval_callback=session_approval_callback)

    result = run_worker(
        registry=registry,
        worker="multi-writer",
        input_data="Write files",
        cli_model=mock_model,
        approval_controller=session_controller,
    )

    # All writes executed, but callback only called once due to session approval
    assert call_count == 1
    assert (sandbox_path / "test.txt").exists()
    assert (sandbox_path / "test.txt").read_text() == "same content"


def test_integration_read_and_write_flow(tmp_path, registry, tool_calling_model_cls):
    """Integration test: worker reads file, processes, writes result."""
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"

    input_cfg = PathConfig(
        root=str(input_path),
        mode="ro",
    )
    output_cfg = PathConfig(
        root=str(output_path),
        mode="rw",
        suffixes=[".txt"],
        write_approval=True,  # Require approval for writes
    )

    definition = WorkerDefinition(
        name="processor",
        instructions="Read input, process, write output",
        sandbox=SandboxConfig(paths={"in": input_cfg, "out": output_cfg}),
        toolsets={"filesystem": {}},
    )
    registry.save_definition(definition)

    # Setup: create input file
    input_path.mkdir(parents=True)
    (input_path / "data.txt").write_text("input data")

    # Mock LLM that reads then writes
    mock_model = tool_calling_model_cls(
        [
            {
                "name": "read_file",
                "args": {"path": "in/data.txt"},
            },
            {
                "name": "write_file",
                "args": {
                    "path": "out/result.txt",
                    "content": "processed: input data",
                },
            },
        ]
    )

    result = run_worker(
        registry=registry,
        worker="processor",
        input_data="Process the data",
        cli_model=mock_model,
        approval_controller=ApprovalController(mode="approve_all"),
    )

    # Verify output file
    assert (output_path / "result.txt").exists()
    assert (output_path / "result.txt").read_text() == "processed: input data"


def test_integration_rejection_stops_workflow(tmp_path, registry, tool_calling_model_cls):
    """Integration test: rejecting first tool stops workflow."""
    sandbox_path = tmp_path / "output"
    path_cfg = PathConfig(
        root=str(sandbox_path),
        mode="rw",
        suffixes=[".txt"],
        write_approval=True,  # Require approval for writes
    )

    definition = WorkerDefinition(
        name="writer",
        instructions="Write files",
        sandbox=SandboxConfig(paths={"out": path_cfg}),
        toolsets={"filesystem": {}},
    )
    registry.save_definition(definition)

    # Mock LLM that tries to make two writes
    mock_model = tool_calling_model_cls(
        [
            {
                "name": "write_file",
                "args": {"path": "out/file1.txt", "content": "First"},
            },
            {
                "name": "write_file",
                "args": {"path": "out/file2.txt", "content": "Second"},
            },
        ]
    )

    # Reject the first call
    def reject_callback(request: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(approved=False, note="User rejected")

    reject_controller = ApprovalController(mode="interactive", approval_callback=reject_callback)

    with pytest.raises(PermissionError, match="User rejected"):
        run_worker(
            registry=registry,
            worker="writer",
            input_data="Write files",
            cli_model=mock_model,
            approval_controller=reject_controller,
        )

    # No files written
    assert not (sandbox_path / "file1.txt").exists()
    assert not (sandbox_path / "file2.txt").exists()
