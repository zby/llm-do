"""Tests for CLI error handling.

These tests verify that errors are handled gracefully with user-friendly messages.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from llm_do.cli.main import main


def create_test_manifest(tmp_path, **overrides):
    """Create a test manifest file with defaults."""
    manifest_data = {
        "version": 1,
        "runtime": {"approval_mode": "approve_all"},
        "entry": {"agent": "main"},
        "agent_files": ["test.agent"],
        **overrides,
    }
    manifest_file = tmp_path / "project.json"
    manifest_file.write_text(json.dumps(manifest_data))

    # Create the worker file
    worker = tmp_path / "test.agent"
    worker.write_text("""---
name: main
---
Test worker
""")

    return manifest_file


class TestCLIManifestErrors:
    """Tests for manifest loading errors."""

    def test_manifest_not_found(self, capsys):
        """Test that missing manifest shows helpful error."""
        with patch("sys.argv", ["llm-do", "nonexistent.json", "hello"]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "not found" in captured.err.lower()

    def test_invalid_json_manifest(self, tmp_path, capsys):
        """Test that invalid JSON manifest shows error."""
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text("not valid json")

        with patch("sys.argv", ["llm-do", str(manifest_file), "hello"]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Invalid JSON" in captured.err

    def test_invalid_manifest_schema(self, tmp_path, capsys):
        """Test that invalid manifest schema shows error."""
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text('{"version": 1}')  # Missing required fields

        with patch("sys.argv", ["llm-do", str(manifest_file), "hello"]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Invalid manifest" in captured.err

    def test_unsupported_manifest_version(self, tmp_path, capsys):
        """Test that unsupported manifest version shows error."""
        manifest_data = {
            "version": 99,
            "runtime": {},
            "entry": {"agent": "main"},
            "agent_files": ["test.agent"],
        }
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text(json.dumps(manifest_data))

        with patch("sys.argv", ["llm-do", str(manifest_file), "hello"]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "version" in captured.err.lower()


    def test_init_python_module_not_found(self, tmp_path, capsys):
        """Test missing --init-python path is reported clearly."""
        manifest_file = create_test_manifest(tmp_path)

        with patch("sys.argv", [
            "llm-do",
            str(manifest_file),
            "hello",
            "--init-python",
            "missing_provider.py",
        ]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Init module not found" in captured.err

    def test_init_python_runtime_error_without_debug_returns_error(self, tmp_path, capsys):
        """Test init module exceptions return exit code 1 by default."""
        manifest_file = create_test_manifest(tmp_path)
        init_module = tmp_path / "broken_init.py"
        init_module.write_text("raise RuntimeError('init boom')\n")

        with patch("sys.argv", [
            "llm-do",
            str(manifest_file),
            "hello",
            "--init-python",
            str(init_module),
        ]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "init boom" in captured.err

    def test_init_python_runtime_error_with_debug_reraises(self, tmp_path):
        """Test init module exceptions are re-raised with --debug."""
        manifest_file = create_test_manifest(tmp_path)
        init_module = tmp_path / "broken_init.py"
        init_module.write_text("raise RuntimeError('init boom')\n")

        with patch("sys.argv", [
            "llm-do",
            str(manifest_file),
            "hello",
            "--init-python",
            str(init_module),
            "--debug",
        ]):
            with pytest.raises(RuntimeError, match="init boom"):
                main()

    def test_init_python_relative_path_resolves_from_cwd(self, tmp_path, capsys, monkeypatch):
        """Test relative --init-python paths are resolved from shell CWD."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        manifest_file = create_test_manifest(project_dir)

        init_module = tmp_path / "cwd_init.py"
        init_module.write_text("raise RuntimeError('cwd relative init loaded')\n")

        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", [
            "llm-do",
            str(manifest_file),
            "hello",
            "--init-python",
            "cwd_init.py",
        ]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "cwd relative init loaded" in captured.err
        assert "Init module not found" not in captured.err

    def test_invalid_input_does_not_run_init_python(self, tmp_path, capsys):
        """Test init modules are not executed when CLI input validation already fails."""
        manifest_file = create_test_manifest(tmp_path)
        init_module = tmp_path / "side_effect_init.py"
        marker = tmp_path / "init_ran.marker"
        init_module.write_text(f"open({str(marker)!r}, 'w').write('ran')\n")

        with patch("sys.argv", [
            "llm-do",
            str(manifest_file),
            "hello",
            "--input-json",
            '{"input":"override"}',
            "--init-python",
            str(init_module),
        ]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Cannot combine prompt argument and --input-json" in captured.err
        assert not marker.exists()


class TestCLIInputErrors:
    """Tests for input handling errors."""

    def test_cli_input_not_allowed(self, tmp_path, capsys):
        """Test that CLI input is rejected when allow_cli_input is false."""
        manifest_data = {
            "version": 1,
            "runtime": {},
            "allow_cli_input": False,
            "entry": {"agent": "main", "args": {"input": "default"}},
            "agent_files": ["test.agent"],
        }
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text(json.dumps(manifest_data))

        worker = tmp_path / "test.agent"
        worker.write_text("---\nname: main\n---\nTest")

        with patch("sys.argv", ["llm-do", str(manifest_file), "override prompt"]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "allow_cli_input" in captured.err

    def test_prompt_and_input_json_mutually_exclusive(self, tmp_path, capsys):
        """Test that prompt and --input-json cannot be combined."""
        manifest_file = create_test_manifest(tmp_path)

        with patch("sys.argv", [
            "llm-do", str(manifest_file),
            "prompt text", "--input-json", '{"input": "json input"}'
        ]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Cannot combine" in captured.err

    def test_invalid_input_json(self, tmp_path, capsys):
        """Test that invalid --input-json shows error."""
        manifest_file = create_test_manifest(tmp_path)

        with patch("sys.argv", ["llm-do", str(manifest_file), "--input-json", "not json"]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Invalid JSON" in captured.err

    def test_input_json_must_be_object(self, tmp_path, capsys):
        """Test that --input-json must be a JSON object."""
        manifest_file = create_test_manifest(tmp_path)

        with patch("sys.argv", ["llm-do", str(manifest_file), "--input-json", '"string"']):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "must be a JSON object" in captured.err

    def test_no_input_provided(self, tmp_path, capsys):
        """Test that missing input shows error."""
        manifest_data = {
            "version": 1,
            "runtime": {},
            "entry": {"agent": "main"},  # No input
            "agent_files": ["test.agent"],
        }
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text(json.dumps(manifest_data))

        worker = tmp_path / "test.agent"
        worker.write_text("---\nname: main\n---\nTest")

        # Force stdin.isatty() to return True
        with patch("sys.argv", ["llm-do", str(manifest_file)]):
            with patch("sys.stdin.isatty", return_value=True):
                exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "No input provided" in captured.err


class TestCLIFlagErrors:
    """Tests for CLI flag validation errors."""

    def test_headless_and_tui_mutually_exclusive(self, tmp_path, capsys):
        """Test that --headless and --tui cannot be combined."""
        manifest_file = create_test_manifest(tmp_path)

        with patch("sys.argv", ["llm-do", str(manifest_file), "--headless", "--tui", "hello"]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Cannot combine --headless and --tui" in captured.err

    def test_chat_requires_tui(self, tmp_path, capsys):
        """Test that --chat requires TUI mode."""
        manifest_file = create_test_manifest(tmp_path)

        with patch("sys.argv", ["llm-do", str(manifest_file), "--chat", "--headless", "hello"]):
            with patch("sys.stdout.isatty", return_value=False):
                exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Chat mode requires TUI" in captured.err


class TestCLIRuntimeErrors:
    """Tests for runtime error handling."""

    def test_missing_model_error(self, tmp_path, monkeypatch):
        """Test that missing model shows helpful error."""
        manifest_file = create_test_manifest(tmp_path)
        monkeypatch.delenv("LLM_DO_MODEL", raising=False)

        with patch("sys.argv", ["llm-do", str(manifest_file), "hello"]):
            exit_code = main()

        assert exit_code == 1

    def test_missing_worker_file(self, tmp_path, capsys):
        """Test that missing worker file shows error."""
        manifest_data = {
            "version": 1,
            "runtime": {"approval_mode": "approve_all"},
            "entry": {"agent": "main"},
            "agent_files": ["missing.agent"],
        }
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text(json.dumps(manifest_data))

        with patch("sys.argv", ["llm-do", str(manifest_file), "hello"]):
            with patch.dict("os.environ", {"LLM_DO_MODEL": "test"}):
                exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "not found" in captured.err.lower()

    def test_entry_agent_not_found_error(self, tmp_path, capsys):
        """Test that missing entry agent shows helpful error."""
        manifest_data = {
            "version": 1,
            "runtime": {"approval_mode": "approve_all"},
            "entry": {"agent": "missing"},
            "agent_files": ["test.agent"],
        }
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text(json.dumps(manifest_data))

        worker = tmp_path / "test.agent"
        worker.write_text("---\nname: main\n---\nTest")

        with patch("sys.argv", ["llm-do", str(manifest_file), "hello"]):
            with patch.dict("os.environ", {"LLM_DO_MODEL": "test"}):
                exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Entry agent 'missing' not found" in captured.err

    def test_keyboard_interrupt_handled(self, tmp_path, capsys):
        """Test that KeyboardInterrupt is handled gracefully."""
        manifest_file = create_test_manifest(tmp_path)

        with patch("llm_do.ui.runner.Runtime.run_entry", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = KeyboardInterrupt()

            with patch("sys.argv", ["llm-do", str(manifest_file), "hello"]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test"}):
                    exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Aborted" in captured.err

    def test_permission_error_handled(self, tmp_path, capsys):
        """Test that PermissionError is handled gracefully."""
        manifest_file = create_test_manifest(tmp_path)

        with patch("llm_do.ui.runner.Runtime.run_entry", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = PermissionError("Tool 'write_file' requires approval")

            with patch("sys.argv", ["llm-do", str(manifest_file), "hello"]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test"}):
                    exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Tool 'write_file'" in captured.err

    def test_model_http_error_handled(self, tmp_path, capsys):
        """Test that ModelHTTPError is handled gracefully."""
        from pydantic_ai.exceptions import ModelHTTPError

        manifest_file = create_test_manifest(tmp_path)

        with patch("llm_do.ui.runner.Runtime.run_entry", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ModelHTTPError(
                status_code=401,
                model_name="test",
                body={"error": {"message": "Invalid API key"}},
            )

            with patch("sys.argv", ["llm-do", str(manifest_file), "hello"]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test"}):
                    exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "401" in captured.err


class TestCLISuccess:
    """Tests for successful CLI execution."""

    def test_success_returns_zero(self, tmp_path, capsys):
        """Test that successful execution returns 0."""
        manifest_file = create_test_manifest(tmp_path)

        mock_ctx = AsyncMock()
        with patch("llm_do.ui.runner.Runtime.run_entry", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("Success!", mock_ctx)

            with patch("sys.argv", ["llm-do", str(manifest_file), "hello"]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test"}):
                    exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == "Success!"

    def test_input_from_manifest(self, tmp_path, capsys):
        """Test using input from manifest entry.args."""
        manifest_data = {
            "version": 1,
            "runtime": {"approval_mode": "approve_all"},
            "entry": {"agent": "main", "args": {"input": "manifest prompt"}},
            "agent_files": ["test.agent"],
        }
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text(json.dumps(manifest_data))

        worker = tmp_path / "test.agent"
        worker.write_text("---\nname: main\n---\nTest")

        mock_ctx = AsyncMock()
        with patch("llm_do.ui.runner.Runtime.run_entry", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("Success!", mock_ctx)

            # No prompt argument - should use manifest input
            with patch("sys.argv", ["llm-do", str(manifest_file)]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test"}):
                    exit_code = main()

        assert exit_code == 0
        # Verify the input data passed to run() is a dict
        call_args = mock_run.call_args
        assert call_args.args[1] == {"input": "manifest prompt"}

    def test_input_json_override(self, tmp_path, capsys):
        """Test --input-json overrides manifest entry.args."""
        manifest_data = {
            "version": 1,
            "runtime": {"approval_mode": "approve_all"},
            "entry": {"agent": "main", "args": {"input": "manifest prompt"}},
            "agent_files": ["test.agent"],
        }
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text(json.dumps(manifest_data))

        worker = tmp_path / "test.agent"
        worker.write_text("---\nname: main\n---\nTest")

        mock_ctx = AsyncMock()
        with patch("llm_do.ui.runner.Runtime.run_entry", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("Success!", mock_ctx)

            # Note: extra fields beyond 'input' and 'attachments' are ignored
            with patch("sys.argv", [
                "llm-do", str(manifest_file),
                "--input-json", '{"input": "json override"}'
            ]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test"}):
                    exit_code = main()

        assert exit_code == 0
        # Input is passed as dict payload
        call_args = mock_run.call_args
        assert call_args.args[1] == {"input": "json override"}


    def test_init_python_registers_custom_provider(self, tmp_path, capsys):
        """Test --init-python can register providers for model resolution."""
        manifest_file = create_test_manifest(tmp_path)

        provider_file = tmp_path / "provider_init.py"
        provider_file.write_text(
            """
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from llm_do import register_model_factory


def _respond(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content="init provider response")])


register_model_factory("init_provider_test", lambda _name: FunctionModel(_respond), replace=True)
"""
        )

        with patch("sys.argv", [
            "llm-do",
            str(manifest_file),
            "hello",
            "--headless",
            "--init-python",
            str(provider_file),
        ]):
            with patch.dict("os.environ", {"LLM_DO_MODEL": "init_provider_test:model"}):
                exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == "init provider response"


class TestCLIDebugFlag:
    """Tests for --debug flag behavior."""

    def test_debug_flag_reraises_exception(self, tmp_path):
        """Test that --debug flag causes exceptions to be re-raised."""
        manifest_file = create_test_manifest(tmp_path)

        with patch("llm_do.ui.runner.Runtime.run_entry", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ValueError("Test error")

            with patch("sys.argv", ["llm-do", str(manifest_file), "hello", "--debug"]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test"}):
                    with pytest.raises(ValueError, match="Test error"):
                        main()
