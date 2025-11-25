"""Integration tests using mocked LLM models with predefined tool calls."""
import json
from pathlib import Path

import pytest

from llm_do import (
    ApprovalDecision,
    SandboxConfig,
    ToolRule,
    WorkerDefinition,
    WorkerRegistry,
    approve_all_callback,
    run_worker,
    strict_mode_callback,
)


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
    sandbox_cfg = SandboxConfig(
        name="out",
        path=sandbox_path,
        mode="rw",
        allowed_suffixes=[".txt"],
    )
    rule = ToolRule(name="sandbox.write", approval_required=True)

    definition = WorkerDefinition(
        name="writer",
        system_prompt="Write a test file",
        sandboxes={"out": sandbox_cfg},
        tool_rules={"sandbox.write": rule},
    )
    registry.save_definition(definition)

    # Mock LLM that calls sandbox_write_text
    mock_model = tool_calling_model_cls(
        [
            {
                "name": "sandbox_write_text",
                "args": {
                    "sandbox": "out",
                    "path": "test.txt",
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
        approval_callback=approve_all_callback,
    )

    # Verify file was written
    assert (sandbox_path / "test.txt").exists()
    assert (sandbox_path / "test.txt").read_text() == "Hello from test!"
    assert result.output == "Task completed"


def test_integration_strict_mode_blocks_write(tmp_path, registry, tool_calling_model_cls):
    """Integration test: worker fails in --strict mode."""
    sandbox_path = tmp_path / "output"
    sandbox_cfg = SandboxConfig(
        name="out",
        path=sandbox_path,
        mode="rw",
        allowed_suffixes=[".txt"],
    )
    rule = ToolRule(name="sandbox.write", approval_required=True)

    definition = WorkerDefinition(
        name="writer",
        system_prompt="Write a test file",
        sandboxes={"out": sandbox_cfg},
        tool_rules={"sandbox.write": rule},
    )
    registry.save_definition(definition)

    # Mock LLM that tries to call sandbox_write_text
    mock_model = tool_calling_model_cls(
        [
            {
                "name": "sandbox_write_text",
                "args": {
                    "sandbox": "out",
                    "path": "test.txt",
                    "content": "Hello from test!",
                },
            }
        ]
    )

    with pytest.raises(PermissionError, match="Strict mode.*sandbox.write"):
        run_worker(
            registry=registry,
            worker="writer",
            input_data="Write a test file",
            cli_model=mock_model,
            approval_callback=strict_mode_callback,
        )

    # Verify file was NOT written
    assert not (sandbox_path / "test.txt").exists()


def test_integration_multiple_tool_calls_with_session_approval(
    tmp_path, registry, tool_calling_model_cls
):
    """Integration test: multiple tool calls with session approval."""
    sandbox_path = tmp_path / "output"
    sandbox_cfg = SandboxConfig(
        name="out",
        path=sandbox_path,
        mode="rw",
        allowed_suffixes=[".txt"],
    )
    rule = ToolRule(name="sandbox.write", approval_required=True)

    definition = WorkerDefinition(
        name="multi-writer",
        system_prompt="Write multiple files",
        sandboxes={"out": sandbox_cfg},
        tool_rules={"sandbox.write": rule},
    )
    registry.save_definition(definition)

    # Mock LLM that makes multiple identical write calls
    # Session approval should work for identical payloads (same args)
    mock_model = tool_calling_model_cls(
        [
            {
                "name": "sandbox_write_text",
                "args": {"sandbox": "out", "path": "test.txt", "content": "same content"},
            },
            {
                "name": "sandbox_write_text",
                "args": {"sandbox": "out", "path": "test.txt", "content": "same content"},
            },
            {
                "name": "sandbox_write_text",
                "args": {"sandbox": "out", "path": "test.txt", "content": "same content"},
            },
        ]
    )

    # Custom callback: approve first call for session
    call_count = 0

    def session_approval_callback(tool_name, payload, reason):
        nonlocal call_count
        call_count += 1
        # First call: approve for session (subsequent identical calls auto-approved)
        return ApprovalDecision(approved=True, approve_for_session=True)

    result = run_worker(
        registry=registry,
        worker="multi-writer",
        input_data="Write files",
        cli_model=mock_model,
        approval_callback=session_approval_callback,
    )

    # All writes executed, but callback only called once due to session approval
    assert call_count == 1
    assert (sandbox_path / "test.txt").exists()
    assert (sandbox_path / "test.txt").read_text() == "same content"


def test_integration_read_and_write_flow(tmp_path, registry, tool_calling_model_cls):
    """Integration test: worker reads file, processes, writes result."""
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"

    input_cfg = SandboxConfig(
        name="in",
        path=input_path,
        mode="ro",
    )
    output_cfg = SandboxConfig(
        name="out",
        path=output_path,
        mode="rw",
        allowed_suffixes=[".txt"],
    )
    rule = ToolRule(name="sandbox.write", approval_required=True)

    definition = WorkerDefinition(
        name="processor",
        system_prompt="Read input, process, write output",
        sandboxes={"in": input_cfg, "out": output_cfg},
        tool_rules={"sandbox.write": rule},
    )
    registry.save_definition(definition)

    # Setup: create input file
    input_path.mkdir(parents=True)
    (input_path / "data.txt").write_text("input data")

    # Mock LLM that reads then writes
    mock_model = tool_calling_model_cls(
        [
            {
                "name": "sandbox_read_text",
                "args": {"sandbox": "in", "path": "data.txt"},
            },
            {
                "name": "sandbox_write_text",
                "args": {
                    "sandbox": "out",
                    "path": "result.txt",
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
        approval_callback=approve_all_callback,
    )

    # Verify output file
    assert (output_path / "result.txt").exists()
    assert (output_path / "result.txt").read_text() == "processed: input data"


def test_integration_rejection_stops_workflow(tmp_path, registry, tool_calling_model_cls):
    """Integration test: rejecting first tool stops workflow."""
    sandbox_path = tmp_path / "output"
    sandbox_cfg = SandboxConfig(
        name="out",
        path=sandbox_path,
        mode="rw",
        allowed_suffixes=[".txt"],
    )
    rule = ToolRule(name="sandbox.write", approval_required=True)

    definition = WorkerDefinition(
        name="writer",
        system_prompt="Write files",
        sandboxes={"out": sandbox_cfg},
        tool_rules={"sandbox.write": rule},
    )
    registry.save_definition(definition)

    # Mock LLM that tries to make two writes
    mock_model = tool_calling_model_cls(
        [
            {
                "name": "sandbox_write_text",
                "args": {"sandbox": "out", "path": "file1.txt", "content": "First"},
            },
            {
                "name": "sandbox_write_text",
                "args": {"sandbox": "out", "path": "file2.txt", "content": "Second"},
            },
        ]
    )

    # Reject the first call
    def reject_callback(tool_name, payload, reason):
        return ApprovalDecision(approved=False, note="User rejected")

    with pytest.raises(PermissionError, match="User rejected"):
        run_worker(
            registry=registry,
            worker="writer",
            input_data="Write files",
            cli_model=mock_model,
            approval_callback=reject_callback,
        )

    # No files written
    assert not (sandbox_path / "file1.txt").exists()
    assert not (sandbox_path / "file2.txt").exists()
