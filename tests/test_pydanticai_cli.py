"""Tests for CLI argument parsing and invocation.

These tests focus on CLI interface behavior, not full worker execution.
Integration tests in test_pydanticai_integration.py cover end-to-end workflows.
"""
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic_ai.messages import FunctionToolResultEvent, ToolReturnPart
from rich.console import Console as RichConsole
from rich.text import Text

from llm_do import WorkerDefinition, WorkerRegistry, WorkerRunResult
from llm_do.cli import _build_streaming_callback, main


def test_cli_parses_worker_name_and_uses_cwd_registry(tmp_path, monkeypatch):
    """Test that CLI defaults to CWD as registry when not specified."""
    # Create worker in workers/ subdirectory
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="test_worker", instructions="demo"))

    # Change to tmp_path directory (simulating user running from project directory)
    monkeypatch.chdir(tmp_path)

    # Mock run_worker to capture how it's called
    with patch("llm_do.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="test output")

        # Run CLI with worker name (no path, no --registry flag)
        result = main(["test_worker", "Hello", "--approve-all"])

        assert result == 0
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs

        # Verify registry defaults to CWD (which is tmp_path)
        assert call_kwargs["registry"].root == tmp_path
        assert call_kwargs["worker"] == "test_worker"
        assert call_kwargs["input_data"] == "Hello"


def test_cli_accepts_plain_text_message(tmp_path, monkeypatch):
    """Test that plain text message is passed as input_data."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="greeter", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    with patch("llm_do.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="Hi there!")

        # Worker is now in workers/ subdirectory by convention
        main(["greeter", "Tell me a joke", "--approve-all"])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["input_data"] == "Tell me a joke"


def test_cli_accepts_json_input_instead_of_message(tmp_path, monkeypatch):
    """Test that --input takes precedence over plain message."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    with patch("llm_do.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="done")

        main([
            "worker",
            "--input",
            '{"task": "analyze", "data": [1,2,3]}',
            "--approve-all",
        ])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["input_data"] == {"task": "analyze", "data": [1, 2, 3]}


def test_cli_input_flag_accepts_plain_text(tmp_path, monkeypatch):
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    with patch("llm_do.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="done")

        main([
            "worker",
            "--input",
            "process all files",
            "--approve-all",
        ])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["input_data"] == "process all files"


def test_cli_accepts_worker_name_with_explicit_registry(tmp_path):
    """Test traditional usage with worker name and --registry flag."""
    registry_dir = tmp_path / "workers"
    registry = WorkerRegistry(registry_dir)
    registry.save_definition(WorkerDefinition(name="myworker", instructions="demo"))

    with patch("llm_do.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="result")

        main([
            "myworker",
            "input",
            "--registry",
            str(registry_dir),
            "--approve-all",
        ])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["registry"].root == registry_dir
        assert call_kwargs["worker"] == "myworker"


def test_cli_passes_model_override(tmp_path, monkeypatch):
    """Test that --model is passed to run_worker."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    with patch("llm_do.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="done")

        main(["worker", "hi", "--model", "openai:gpt-4o", "--approve-all"])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["cli_model"] == "openai:gpt-4o"


def test_cli_passes_attachments(tmp_path, monkeypatch):
    """Test that --attachments are passed to run_worker."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    # Create attachment files
    (tmp_path / "file1.txt").write_text("content1")
    (tmp_path / "file2.txt").write_text("content2")

    monkeypatch.chdir(tmp_path)

    with patch("llm_do.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="done")

        main([
            "worker",
            "process",
            "--attachments",
            str(tmp_path / "file1.txt"),
            str(tmp_path / "file2.txt"),
            "--approve-all",
        ])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["attachments"] == [
            str(tmp_path / "file1.txt"),
            str(tmp_path / "file2.txt"),
        ]


def test_cli_displays_rich_output_by_default(tmp_path, monkeypatch):
    """Default mode renders the rich message exchange and final panel."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    recorded_console: dict[str, RichConsole] = {}

    def fake_console(*_args, **_kwargs):
        console = RichConsole(
            force_terminal=False,
            color_system=None,
            record=True,
            width=80,
        )
        recorded_console["instance"] = console
        return console

    monkeypatch.setattr("llm_do.cli.Console", fake_console)

    with patch("llm_do.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output={"key": "value", "nested": {"a": 1}})

        assert main(["worker", "test", "--approve-all"]) == 0

    assert "instance" in recorded_console
    rendered = recorded_console["instance"].export_text()
    assert "Message Exchange" in rendered
    assert "Final Output" in rendered
    assert '"key": "value"' in rendered


def test_cli_json_mode_outputs_structured_result(tmp_path, monkeypatch, capsys):
    """--json flag should return serialized WorkerRunResult."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    with patch("llm_do.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(
            output={"key": "value"},
            messages=[{"role": "user", "content": "hello"}],
        )

        assert main(["worker", "test", "--json", "--approve-all"]) == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["output"] == {"key": "value"}
    assert payload["messages"] == [{"role": "user", "content": "hello"}]


def test_streaming_callback_renders_tool_results(monkeypatch):
    """Regression test: tool result events render via the shared helper."""

    console = RichConsole(
        force_terminal=False,
        color_system=None,
        record=True,
        width=80,
    )

    mock_render = Mock(return_value=Text("rendered"))
    monkeypatch.setattr("llm_do.cli_display.render_json_or_text", mock_render)

    callback = _build_streaming_callback(console)

    tool_result = ToolReturnPart(tool_name="math", content={"value": 42})
    event = FunctionToolResultEvent(result=tool_result)

    callback([event])

    mock_render.assert_called_once_with({"value": 42})


def test_cli_uses_interactive_approval_when_tty(tmp_path, monkeypatch):
    """Default approval path should build the interactive callback."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("llm_do.cli._is_interactive_terminal", lambda: True)

    sentinel = object()

    with patch(
        "llm_do.cli._build_interactive_approval_controller",
        return_value=sentinel,
    ) as mock_builder, patch("llm_do.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="ok")

        assert main(["worker", "hello"]) == 0

    mock_builder.assert_called_once()
    assert mock_run.call_args.kwargs["approval_controller"] is sentinel


def test_cli_requires_tty_for_interactive_mode(tmp_path, monkeypatch, capsys):
    """When no approval flags are provided, a TTY is required."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("llm_do.cli._is_interactive_terminal", lambda: False)

    with patch("llm_do.cli.run_worker") as mock_run:
        assert main(["worker", "task"]) == 1
        mock_run.assert_not_called()

    captured = capsys.readouterr()
    assert "interactive approvals require a TTY" in captured.err


def test_cli_init_creates_project(tmp_path):
    """Test that 'llm-do init' creates a project structure."""
    from llm_do.cli import init_project

    project_dir = tmp_path / "my-project"

    result = init_project([str(project_dir), "--name", "My Project", "--model", "anthropic:claude-haiku-4-5"])

    assert result == 0
    assert project_dir.exists()
    assert (project_dir / "main.worker").exists()
    assert (project_dir / "project.yaml").exists()

    # Check main.worker content
    main_content = (project_dir / "main.worker").read_text()
    assert "name: main" in main_content
    assert "My Project" in main_content

    # Check project.yaml content
    project_content = (project_dir / "project.yaml").read_text()
    assert "name: My Project" in project_content
    assert "model: anthropic:claude-haiku-4-5" in project_content


def test_cli_init_fails_if_exists(tmp_path):
    """Test that 'llm-do init' fails if project already exists."""
    from llm_do.cli import init_project

    # Create existing main.worker
    (tmp_path / "main.worker").write_text("existing")

    result = init_project([str(tmp_path)])

    assert result == 1


def test_cli_init_minimal(tmp_path):
    """Test that 'llm-do init' works with minimal args."""
    from llm_do.cli import init_project

    project_dir = tmp_path / "simple"

    result = init_project([str(project_dir)])

    assert result == 0
    assert (project_dir / "main.worker").exists()
    # No project.yaml without --name or --model
    assert not (project_dir / "project.yaml").exists()
