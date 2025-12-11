"""Tests for async CLI argument parsing and invocation.

These tests focus on CLI interface behavior, not full worker execution.
"""
import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from llm_do import WorkerDefinition, WorkerRegistry, WorkerRunResult
from llm_do.cli_async import main, parse_args, run_async_cli


def test_parse_args_worker_and_message():
    """Test basic argument parsing."""
    args = parse_args(["myworker", "hello world"])
    assert args.worker == "myworker"
    assert args.message == "hello world"


def test_parse_args_json_flag():
    """Test --json flag parsing."""
    args = parse_args(["worker", "--json", "--approve-all"])
    assert args.json is True
    assert args.approve_all is True


def test_parse_args_approve_modes():
    """Test approval mode flags."""
    args = parse_args(["worker", "--approve-all"])
    assert args.approve_all is True
    assert args.strict is False

    args = parse_args(["worker", "--strict"])
    assert args.strict is True
    assert args.approve_all is False


def test_parse_args_model_override():
    """Test --model flag."""
    args = parse_args(["worker", "--model", "openai:gpt-4o"])
    assert args.cli_model == "openai:gpt-4o"


def test_parse_args_config_overrides():
    """Test --set flags for config overrides."""
    args = parse_args(["worker", "--set", "model=test", "--set", "sandbox.enabled=true"])
    assert args.config_overrides == ["model=test", "sandbox.enabled=true"]


def test_async_cli_parses_worker_and_runs(tmp_path, monkeypatch):
    """Test that async CLI parses worker and calls run_worker_async."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="test_worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_worker_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(output="test output")

            result = await run_async_cli(["test_worker", "Hello", "--approve-all"])

            assert result == 0
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["registry"].root == tmp_path
            assert call_kwargs["worker"] == "test_worker"
            assert call_kwargs["input_data"] == "Hello"

    asyncio.run(run_test())


def test_async_cli_json_output(tmp_path, monkeypatch, capsys):
    """Test --json flag outputs structured result."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_worker_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(
                output={"key": "value"},
                messages=[{"role": "user", "content": "hello"}],
            )

            result = await run_async_cli(["worker", "test", "--json", "--approve-all"])
            assert result == 0

    asyncio.run(run_test())

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["output"] == {"key": "value"}
    assert payload["messages"] == [{"role": "user", "content": "hello"}]


def test_async_cli_model_override(tmp_path, monkeypatch):
    """Test --model is passed to run_worker_async."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_worker_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(output="done")

            await run_async_cli(["worker", "hi", "--model", "openai:gpt-4o", "--approve-all"])

            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["cli_model"] == "openai:gpt-4o"

    asyncio.run(run_test())


def test_async_cli_attachments(tmp_path, monkeypatch):
    """Test --attachments are passed to run_worker_async."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    (tmp_path / "file1.txt").write_text("content1")

    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_worker_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(output="done")

            await run_async_cli([
                "worker",
                "process",
                "--attachments",
                str(tmp_path / "file1.txt"),
                "--approve-all",
            ])

            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["attachments"] == [str(tmp_path / "file1.txt")]

    asyncio.run(run_test())


def test_async_cli_json_input(tmp_path, monkeypatch):
    """Test --input accepts JSON payload."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_worker_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(output="done")

            await run_async_cli([
                "worker",
                "--input",
                '{"task": "analyze"}',
                "--approve-all",
            ])

            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["input_data"] == {"task": "analyze"}

    asyncio.run(run_test())


def test_async_cli_rejects_conflicting_approval_modes(tmp_path, monkeypatch, capsys):
    """Test that --approve-all and --strict cannot be used together."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        result = await run_async_cli(["worker", "test", "--approve-all", "--strict"])
        return result

    result = asyncio.run(run_test())

    assert result == 1
    captured = capsys.readouterr()
    assert "Cannot use --approve-all and --strict together" in captured.err


def test_async_cli_requires_approval_mode_for_json(tmp_path, monkeypatch, capsys):
    """Test that --json mode requires --approve-all or --strict."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        result = await run_async_cli(["worker", "test", "--json"])
        return result

    result = asyncio.run(run_test())

    assert result == 1
    captured = capsys.readouterr()
    assert "JSON mode requires --approve-all or --strict" in captured.err


def test_main_handles_init_subcommand(tmp_path, monkeypatch):
    """Test that main() delegates 'init' to sync CLI."""
    monkeypatch.setattr("sys.argv", ["llm-do", "init", str(tmp_path / "program")])

    # Patch at the cli module level since that's where init_program is defined
    with patch("llm_do.cli.init_program") as mock_init:
        mock_init.return_value = 0
        result = main()

    assert result == 0
    mock_init.assert_called_once_with([str(tmp_path / "program")])


def test_main_runs_async_cli(tmp_path, monkeypatch):
    """Test that main() runs run_async_cli for normal invocations."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["llm-do", "worker", "hello", "--approve-all"])

    with patch("llm_do.cli_async.run_worker_async", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = WorkerRunResult(output="done")
        result = main()

    assert result == 0


def test_parse_args_headless_flag():
    """Test --headless flag parsing."""
    args = parse_args(["worker", "--headless", "--approve-all"])
    assert args.headless is True


def test_async_cli_rejects_combined_json_headless(tmp_path, monkeypatch, capsys):
    """Test that --json and --headless cannot be combined."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_json_headless():
        return await run_async_cli(["worker", "test", "--json", "--headless", "--approve-all"])

    result = asyncio.run(run_json_headless())
    assert result == 1
    captured = capsys.readouterr()
    assert "Cannot combine --json and --headless" in captured.err


def test_async_cli_headless_requires_approval_mode(tmp_path, monkeypatch, capsys):
    """Test that --headless mode requires --approve-all or --strict."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        return await run_async_cli(["worker", "test", "--headless"])

    result = asyncio.run(run_test())
    assert result == 1
    captured = capsys.readouterr()
    assert "Headless mode requires --approve-all or --strict" in captured.err


def test_async_cli_headless_with_approve_all(tmp_path, monkeypatch):
    """Test that --headless works with --approve-all."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="worker", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_worker_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(output="done")
            return await run_async_cli(["worker", "test", "--headless", "--approve-all"])

    result = asyncio.run(run_test())
    assert result == 0
