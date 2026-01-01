"""Tests for CLI error handling in ctx_runtime.

These tests verify that errors are handled gracefully with user-friendly messages.
"""
from unittest.mock import AsyncMock, patch

import pytest

from llm_do.ctx_runtime.cli import main, run


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_missing_model_error(self, tmp_path, monkeypatch):
        """Test that missing model shows helpful error."""
        # Create a minimal worker file
        worker = tmp_path / "test.worker"
        worker.write_text("""---
name: main
---
Test worker
""")

        # Clear the model env var
        monkeypatch.delenv("LLM_DO_MODEL", raising=False)

        # Mock sys.argv
        with patch("sys.argv", ["llm-do", str(worker), "hello"]):
            exit_code = main()

        assert exit_code == 1

    def test_approve_all_and_reject_all_are_mutually_exclusive(self, tmp_path, capsys):
        """Test that --approve-all and --reject-all cannot be combined."""
        worker = tmp_path / "test.worker"
        worker.write_text("""---
name: main
---
Test worker
""")

        with patch("sys.argv", ["llm-do", str(worker), "--approve-all", "--reject-all", "hello"]):
            with patch.dict("os.environ", {"LLM_DO_MODEL": "test-model"}):
                exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Cannot combine --approve-all and --reject-all" in captured.err

    def test_reject_all_flag_passed_to_run(self, tmp_path):
        """Test that --reject-all is accepted and passed through to run()."""
        worker = tmp_path / "test.worker"
        worker.write_text("""---
name: main
---
Test worker
""")

        mock_ctx = AsyncMock()
        with patch("llm_do.ctx_runtime.cli.run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("Success!", mock_ctx)

            with patch("sys.argv", ["llm-do", str(worker), "--reject-all", "hello"]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test-model"}):
                    exit_code = main()

        assert exit_code == 0
        assert mock_run.call_args.kwargs["reject_all"] is True

    def test_invalid_worker_file_error(self, tmp_path):
        """Test that invalid worker file shows helpful error."""
        # Create an invalid worker file (missing frontmatter)
        worker = tmp_path / "test.worker"
        worker.write_text("No frontmatter here")

        with patch("sys.argv", ["llm-do", str(worker), "hello"]):
            with patch.dict("os.environ", {"LLM_DO_MODEL": "test-model"}):
                exit_code = main()

        assert exit_code == 1

    def test_unknown_entry_error(self, tmp_path):
        """Test that unknown entry point shows helpful error."""
        worker = tmp_path / "test.worker"
        worker.write_text("""---
name: main
---
Test worker
""")

        with patch("sys.argv", ["llm-do", str(worker), "--entry", "nonexistent", "hello"]):
            with patch.dict("os.environ", {"LLM_DO_MODEL": "test-model"}):
                exit_code = main()

        assert exit_code == 1

    def test_keyboard_interrupt_handled(self, tmp_path):
        """Test that KeyboardInterrupt is handled gracefully."""
        worker = tmp_path / "test.worker"
        worker.write_text("""---
name: main
---
Test worker
""")

        # Mock run() to raise KeyboardInterrupt
        with patch("llm_do.ctx_runtime.cli.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = KeyboardInterrupt()

            with patch("sys.argv", ["llm-do", str(worker), "hello"]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test-model"}):
                    exit_code = main()

        assert exit_code == 1

    def test_permission_error_handled(self, tmp_path):
        """Test that PermissionError (approval denied) is handled gracefully."""
        worker = tmp_path / "test.worker"
        worker.write_text("""---
name: main
---
Test worker
""")

        # Mock run() to raise PermissionError
        with patch("llm_do.ctx_runtime.cli.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = PermissionError("Tool 'write_file' requires approval")

            with patch("sys.argv", ["llm-do", str(worker), "hello"]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test-model"}):
                    exit_code = main()

        assert exit_code == 1

    def test_missing_worker_file_error(self, capsys):
        """Test that missing worker files show a helpful error."""
        missing_worker = "missing.worker"

        with patch("sys.argv", ["llm-do", missing_worker, "hello"]):
            with pytest.raises(SystemExit) as excinfo:
                main()

        assert excinfo.value.code == 2
        captured = capsys.readouterr()
        assert "File not found:" in captured.err
        assert missing_worker in captured.err

    def test_model_http_error_handled(self, tmp_path):
        """Test that ModelHTTPError is handled gracefully."""
        from pydantic_ai.exceptions import ModelHTTPError

        worker = tmp_path / "test.worker"
        worker.write_text("""---
name: main
---
Test worker
""")

        # Mock run() to raise ModelHTTPError
        with patch("llm_do.ctx_runtime.cli.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ModelHTTPError(
                status_code=401,
                model_name="test-model",
                body={"error": {"message": "Invalid API key"}},
            )

            with patch("sys.argv", ["llm-do", str(worker), "hello"]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test-model"}):
                    exit_code = main()

        assert exit_code == 1

    def test_success_returns_zero(self, tmp_path):
        """Test that successful execution returns 0."""
        worker = tmp_path / "test.worker"
        worker.write_text("""---
name: main
---
Test worker
""")

        # Mock run() to return successfully
        mock_ctx = AsyncMock()
        with patch("llm_do.ctx_runtime.cli.run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("Success!", mock_ctx)

            with patch("sys.argv", ["llm-do", str(worker), "hello"]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test-model"}):
                    exit_code = main()

        assert exit_code == 0

    def test_streaming_suppresses_stdout(self, tmp_path, capsys):
        """Test that streaming mode does not print the final result."""
        worker = tmp_path / "test.worker"
        worker.write_text("""---
name: main
---
Test worker
""")

        mock_ctx = AsyncMock()
        with patch("llm_do.ctx_runtime.cli.run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("Success!", mock_ctx)

            with patch("sys.argv", ["llm-do", str(worker), "-vv", "hello"]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test-model"}):
                    exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == ""


class TestCLIDebugFlag:
    """Tests for --debug flag behavior."""

    def test_debug_flag_reraises_exception(self, tmp_path):
        """Test that --debug flag causes exceptions to be re-raised."""
        worker = tmp_path / "test.worker"
        worker.write_text("""---
name: main
---
Test worker
""")

        # Mock run() to raise ValueError
        with patch("llm_do.ctx_runtime.cli.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ValueError("Test error")

            with patch("sys.argv", ["llm-do", str(worker), "hello", "--debug"]):
                with patch.dict("os.environ", {"LLM_DO_MODEL": "test-model"}):
                    with pytest.raises(ValueError, match="Test error"):
                        main()
