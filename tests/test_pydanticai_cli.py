"""Tests for CLI argument parsing and invocation.

These tests focus on CLI interface behavior, not full worker execution.
Integration tests in test_pydanticai_integration.py cover end-to-end workflows.
"""
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from llm_do.pydanticai import WorkerDefinition, WorkerRegistry, WorkerRunResult
from llm_do.pydanticai.cli import main


def test_cli_parses_worker_name_and_uses_cwd_registry(tmp_path, monkeypatch):
    """Test that CLI defaults to CWD as registry when not specified."""
    # Create worker in workers/ subdirectory
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="test_worker", instructions="demo"))

    # Change to tmp_path directory (simulating user running from project directory)
    monkeypatch.chdir(tmp_path)

    # Mock run_worker to capture how it's called
    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="test output")

        # Run CLI with worker name (no path, no --registry flag)
        result = main(["test_worker", "Hello"])

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

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="Hi there!")

        # Worker is now in workers/ subdirectory by convention
        main(["greeter", "Tell me a joke"])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["input_data"] == "Tell me a joke"


def test_cli_accepts_json_input_instead_of_message(tmp_path, monkeypatch):
    """Test that --input takes precedence over plain message."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="done")

        main(["worker", "--input", '{"task": "analyze", "data": [1,2,3]}'])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["input_data"] == {"task": "analyze", "data": [1, 2, 3]}


def test_cli_accepts_worker_name_with_explicit_registry(tmp_path):
    """Test traditional usage with worker name and --registry flag."""
    registry_dir = tmp_path / "workers"
    registry = WorkerRegistry(registry_dir)
    registry.save_definition(WorkerDefinition(name="myworker", instructions="demo"))

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="result")

        main(["myworker", "input", "--registry", str(registry_dir)])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["registry"].root == registry_dir
        assert call_kwargs["worker"] == "myworker"


def test_cli_passes_model_override(tmp_path, monkeypatch):
    """Test that --model is passed to run_worker."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="done")

        main(["worker", "hi", "--model", "openai:gpt-4o"])

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

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output="done")

        main([
            "worker",
            "process",
            "--attachments",
            str(tmp_path / "file1.txt"),
            str(tmp_path / "file2.txt"),
        ])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["attachments"] == [
            str(tmp_path / "file1.txt"),
            str(tmp_path / "file2.txt"),
        ]


def test_cli_pretty_prints_by_default(tmp_path, monkeypatch, capsys):
    """Test that output is pretty-printed by default."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output={"key": "value", "nested": {"a": 1}})

        main(["worker", "test"])

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        # Verify it's valid JSON
        assert output["output"] == {"key": "value", "nested": {"a": 1}}

        # Verify it has indentation (pretty printed)
        assert "  " in captured.out  # Has indentation
        assert "\n" in captured.out  # Has newlines


def test_cli_respects_no_pretty_flag(tmp_path, monkeypatch, capsys):
    """Test that --no-pretty disables pretty printing."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    with patch("llm_do.pydanticai.cli.run_worker") as mock_run:
        mock_run.return_value = WorkerRunResult(output={"key": "value"})

        main(["worker", "test", "--no-pretty"])

        captured = capsys.readouterr()
        # Should be compact JSON on one line
        assert captured.out.count("\n") == 1  # Only trailing newline
        assert "  " not in captured.out  # No indentation
