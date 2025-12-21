"""Tests for async CLI argument parsing and invocation.

These tests focus on CLI interface behavior, not full worker execution.
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from llm_do import WorkerDefinition, WorkerRegistry, WorkerRunResult
from llm_do.cli_async import init_project, main, parse_args, run_async_cli, run_oauth_cli
from llm_do.oauth.storage import (
    OAuthCredentials,
    reset_oauth_storage,
    save_oauth_credentials,
    set_oauth_storage,
)


def test_parse_args_message_only():
    """Test basic argument parsing with just message (uses default tool 'main')."""
    args = parse_args(["hello world"])
    assert args.tool == "main"
    assert args.message == "hello world"


def test_parse_args_with_tool_flag():
    """Test argument parsing with explicit --tool flag."""
    args = parse_args(["--tool", "mytool", "hello world"])
    assert args.tool == "mytool"
    assert args.message == "hello world"


def test_parse_args_with_dir_flag():
    """Test argument parsing with --dir flag."""
    args = parse_args(["--dir", "/some/path", "hello world"])
    assert args.dir == Path("/some/path")
    assert args.message == "hello world"


def test_parse_args_with_dir_and_tool():
    """Test argument parsing with both --dir and --tool flags."""
    args = parse_args(["--dir", "/some/path", "--tool", "analyzer", "hello world"])
    assert args.dir == Path("/some/path")
    assert args.tool == "analyzer"
    assert args.message == "hello world"


def test_parse_args_json_flag():
    """Test --json flag parsing."""
    args = parse_args(["--json", "--approve-all"])
    assert args.json is True
    assert args.approve_all is True


def test_parse_args_approve_modes():
    """Test approval mode flags."""
    args = parse_args(["--approve-all"])
    assert args.approve_all is True
    assert args.strict is False

    args = parse_args(["--strict"])
    assert args.strict is True
    assert args.approve_all is False


def test_parse_args_model_override():
    """Test --model flag."""
    args = parse_args(["--model", "openai:gpt-4o"])
    assert args.cli_model == "openai:gpt-4o"


def test_parse_args_config_overrides():
    """Test --set flags for config overrides."""
    args = parse_args(["--set", "model=test", "--set", "sandbox.enabled=true"])
    assert args.config_overrides == ["model=test", "sandbox.enabled=true"]


def test_async_cli_parses_tool_and_runs(tmp_path, monkeypatch):
    """Test that async CLI parses tool and calls run_tool_async."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_tool_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(output="test output")

            result = await run_async_cli(["Hello", "--approve-all"])

            assert result == 0
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["registry"].root == tmp_path
            assert call_kwargs["tool"] == "main"
            assert call_kwargs["input_data"] == "Hello"

    asyncio.run(run_test())


def test_async_cli_with_tool_flag(tmp_path, monkeypatch):
    """Test that async CLI parses --tool flag correctly."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="test_tool", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_tool_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(output="test output")

            result = await run_async_cli(["--tool", "test_tool", "Hello", "--approve-all"])

            assert result == 0
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["tool"] == "test_tool"
            assert call_kwargs["input_data"] == "Hello"

    asyncio.run(run_test())


def test_async_cli_with_dir_flag(tmp_path, monkeypatch):
    """Test that async CLI uses --dir flag for registry root."""
    # Create worker in a subdirectory
    worker_dir = tmp_path / "workers"
    worker_dir.mkdir()
    registry = WorkerRegistry(worker_dir)
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))

    # Run from tmp_path but point to worker_dir
    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_tool_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(output="test output")

            result = await run_async_cli(["--dir", str(worker_dir), "Hello", "--approve-all"])

            assert result == 0
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["registry"].root == worker_dir

    asyncio.run(run_test())


def test_async_cli_json_output(tmp_path, monkeypatch, capsys):
    """Test --json flag outputs structured result."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_tool_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(
                output={"key": "value"},
                messages=[{"role": "user", "content": "hello"}],
            )

            result = await run_async_cli(["test", "--json", "--approve-all"])
            assert result == 0

    asyncio.run(run_test())

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["output"] == {"key": "value"}
    assert payload["messages"] == [{"role": "user", "content": "hello"}]


def test_async_cli_model_override(tmp_path, monkeypatch):
    """Test --model is passed to run_tool_async."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_tool_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(output="done")

            await run_async_cli(["hi", "--model", "openai:gpt-4o", "--approve-all"])

            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["cli_model"] == "openai:gpt-4o"

    asyncio.run(run_test())


def test_async_cli_attachments(tmp_path, monkeypatch):
    """Test --attachments are passed to run_tool_async."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))

    (tmp_path / "file1.txt").write_text("content1")

    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_tool_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(output="done")

            await run_async_cli([
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
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_tool_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(output="done")

            await run_async_cli([
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
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        result = await run_async_cli(["test", "--approve-all", "--strict"])
        return result

    result = asyncio.run(run_test())

    assert result == 1
    captured = capsys.readouterr()
    assert "Cannot use --approve-all and --strict together" in captured.err


def test_async_cli_requires_approval_mode_for_json(tmp_path, monkeypatch, capsys):
    """Test that --json mode requires --approve-all or --strict."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        result = await run_async_cli(["test", "--json"])
        return result

    result = asyncio.run(run_test())

    assert result == 1
    captured = capsys.readouterr()
    assert "JSON mode requires --approve-all or --strict" in captured.err


def test_main_handles_init_subcommand(tmp_path, monkeypatch):
    """Test that main() delegates 'init' to init_project."""
    monkeypatch.setattr("sys.argv", ["llm-do", "init", str(tmp_path / "project")])

    with patch("llm_do.cli_async.init_project") as mock_init:
        mock_init.return_value = 0
        result = main()

    assert result == 0
    mock_init.assert_called_once_with([str(tmp_path / "project")])


def test_cli_init_creates_project(tmp_path):
    """Test that 'llm-do init' creates a main.worker file."""
    project_dir = tmp_path / "my-project"

    result = init_project(
        [str(project_dir), "--name", "my-project", "--model", "anthropic:claude-haiku-4-5"]
    )

    assert result == 0
    assert project_dir.exists()
    assert (project_dir / "main.worker").exists()

    worker_content = (project_dir / "main.worker").read_text()
    assert "name: main" in worker_content
    assert "description: A helpful assistant for my-project" in worker_content
    assert "model: anthropic:claude-haiku-4-5" in worker_content


def test_cli_init_fails_if_exists(tmp_path):
    """Test that 'llm-do init' fails if main.worker already exists."""
    (tmp_path / "main.worker").write_text("existing")

    result = init_project([str(tmp_path)])

    assert result == 1


def test_cli_init_minimal(tmp_path):
    """Test that 'llm-do init' works with minimal args."""
    project_dir = tmp_path / "simple"

    result = init_project([str(project_dir)])

    assert result == 0
    assert (project_dir / "main.worker").exists()


def test_main_runs_async_cli(tmp_path, monkeypatch):
    """Test that main() runs run_async_cli for normal invocations."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["llm-do", "hello", "--approve-all"])

    with patch("llm_do.cli_async.run_tool_async", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = WorkerRunResult(output="done")
        result = main()

    assert result == 0


def test_parse_args_headless_flag():
    """Test --headless flag parsing."""
    args = parse_args(["--headless", "--approve-all"])
    assert args.headless is True


def test_async_cli_rejects_combined_json_headless(tmp_path, monkeypatch, capsys):
    """Test that --json and --headless cannot be combined."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_json_headless():
        return await run_async_cli(["test", "--json", "--headless", "--approve-all"])

    result = asyncio.run(run_json_headless())
    assert result == 1
    captured = capsys.readouterr()
    assert "Cannot combine --json and --headless" in captured.err


def test_async_cli_headless_requires_approval_mode(tmp_path, monkeypatch, capsys):
    """Test that --headless mode requires --approve-all or --strict."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        return await run_async_cli(["test", "--headless"])

    result = asyncio.run(run_test())
    assert result == 1
    captured = capsys.readouterr()
    assert "Headless mode requires --approve-all or --strict" in captured.err


def test_async_cli_headless_with_approve_all(tmp_path, monkeypatch):
    """Test that --headless works with --approve-all."""
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))

    monkeypatch.chdir(tmp_path)

    async def run_test():
        with patch("llm_do.cli_async.run_tool_async", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = WorkerRunResult(output="done")
            return await run_async_cli(["test", "--headless", "--approve-all"])

    result = asyncio.run(run_test())
    assert result == 0


def test_oauth_logout_no_credentials(capsys):
    async def run_test():
        return await run_oauth_cli(["logout", "--provider", "anthropic"])

    result = asyncio.run(run_test())
    assert result == 0
    captured = capsys.readouterr()
    assert "No OAuth credentials found" in captured.out


def test_oauth_logout_clears_credentials(capsys):
    class InMemoryStorage:
        def __init__(self) -> None:
            self._storage = {}

        def load(self):
            return dict(self._storage)

        def save(self, storage):
            self._storage = dict(storage)

    storage = InMemoryStorage()
    set_oauth_storage(storage)
    try:
        save_oauth_credentials(
            "anthropic",
            OAuthCredentials(refresh="refresh", access="access", expires=0),
        )

        async def run_test():
            return await run_oauth_cli(["logout", "--provider", "anthropic"])

        result = asyncio.run(run_test())
    finally:
        reset_oauth_storage()

    assert result == 0
    captured = capsys.readouterr()
    assert "Cleared OAuth credentials" in captured.out
