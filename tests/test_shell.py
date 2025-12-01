"""Tests for shell command execution and pattern matching."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import Mock

from llm_do.shell import (
    BLOCKED_METACHARACTERS,
    MAX_OUTPUT_BYTES,
    ShellBlockedError,
    ShellError,
    check_metacharacters,
    enhance_error_with_sandbox_context,
    execute_shell,
    extract_path_arguments,
    match_shell_rules,
    parse_command,
    validate_paths_in_sandbox,
)
from llm_do.types import ShellResult
from llm_do.filesystem_sandbox import FileSandboxError


class TestParseCommand:
    """Tests for shlex command parsing."""

    def test_simple_command(self):
        assert parse_command("ls -la") == ["ls", "-la"]

    def test_quoted_arguments(self):
        assert parse_command('echo "hello world"') == ["echo", "hello world"]

    def test_single_quotes(self):
        assert parse_command("echo 'hello world'") == ["echo", "hello world"]

    def test_empty_command(self):
        assert parse_command("") == []

    def test_unclosed_quote_raises(self):
        with pytest.raises(ShellBlockedError, match="Cannot parse"):
            parse_command('echo "unclosed')

    def test_complex_command(self):
        assert parse_command("git commit -m 'fix bug'") == ["git", "commit", "-m", "fix bug"]


class TestCheckMetacharacters:
    """Tests for shell metacharacter blocking."""

    def test_clean_command_passes(self):
        check_metacharacters("ls -la /tmp")
        check_metacharacters("git status")
        check_metacharacters("echo hello")

    @pytest.mark.parametrize("char", ['|', '>', '<', ';', '&', '`'])
    def test_single_char_blocked(self, char):
        with pytest.raises(ShellBlockedError, match=f"blocked metacharacter '{char}'"):
            check_metacharacters(f"echo {char} test")

    def test_subshell_blocked(self):
        with pytest.raises(ShellBlockedError, match="blocked metacharacter"):
            check_metacharacters("echo $(whoami)")

    def test_variable_expansion_blocked(self):
        with pytest.raises(ShellBlockedError, match="blocked metacharacter"):
            check_metacharacters("echo ${HOME}")

    def test_pipe_blocked(self):
        with pytest.raises(ShellBlockedError, match="blocked metacharacter '|'"):
            check_metacharacters("cat file | grep pattern")

    def test_redirect_blocked(self):
        with pytest.raises(ShellBlockedError, match="blocked metacharacter '>'"):
            check_metacharacters("echo hello > file.txt")


class TestExtractPathArguments:
    """Tests for path argument extraction."""

    def test_no_paths(self):
        assert extract_path_arguments(["ls"]) == []

    def test_single_path(self):
        assert extract_path_arguments(["cat", "file.txt"]) == ["file.txt"]

    def test_multiple_paths(self):
        assert extract_path_arguments(["cp", "src.txt", "dst.txt"]) == ["src.txt", "dst.txt"]

    def test_skips_flags(self):
        assert extract_path_arguments(["ls", "-la", "/tmp"]) == ["/tmp"]
        assert extract_path_arguments(["cat", "-n", "--number", "file.txt"]) == ["file.txt"]

    def test_skips_empty_args(self):
        assert extract_path_arguments(["echo", "", "hello"]) == ["hello"]


class TestMatchShellRules:
    """Tests for shell rule pattern matching."""

    def test_exact_match(self):
        rules = [{"pattern": "git status", "approval_required": False, "allowed": True}]
        allowed, approval = match_shell_rules("git status", ["git", "status"], rules, None, None)
        assert allowed is True
        assert approval is False

    def test_prefix_match(self):
        rules = [{"pattern": "git", "approval_required": False, "allowed": True}]
        allowed, approval = match_shell_rules("git status", ["git", "status"], rules, None, None)
        assert allowed is True
        assert approval is False

    def test_no_match_uses_default(self):
        rules = [{"pattern": "git", "approval_required": False, "allowed": True}]
        default = {"allowed": True, "approval_required": True}
        allowed, approval = match_shell_rules("ls -la", ["ls", "-la"], rules, default, None)
        assert allowed is True
        assert approval is True

    def test_no_match_no_default_fallback(self):
        rules = [{"pattern": "git", "approval_required": False, "allowed": True}]
        allowed, approval = match_shell_rules("ls -la", ["ls", "-la"], rules, None, None)
        assert allowed is True
        assert approval is True  # Ultimate fallback

    def test_first_match_wins(self):
        rules = [
            {"pattern": "git status", "approval_required": False, "allowed": True},
            {"pattern": "git", "approval_required": True, "allowed": True},
        ]
        allowed, approval = match_shell_rules("git status", ["git", "status"], rules, None, None)
        assert approval is False  # First rule wins

    def test_blocked_command(self):
        rules = [{"pattern": "rm", "approval_required": False, "allowed": False}]
        allowed, approval = match_shell_rules("rm -rf /", ["rm", "-rf", "/"], rules, None, None)
        assert allowed is False


class TestValidatePathsInSandbox:
    """Tests for path validation against sandbox."""

    def test_no_paths_always_valid(self):
        mock_sandbox = Mock()
        assert validate_paths_in_sandbox([], ["output"], mock_sandbox) is True

    def test_no_allowed_sandboxes_always_valid(self):
        mock_sandbox = Mock()
        assert validate_paths_in_sandbox(["/some/path"], [], mock_sandbox) is True

    def test_valid_path_in_sandbox(self):
        mock_sandbox = Mock()
        mock_sandbox.resolve.return_value = Path("/sandbox/output/file.txt")
        mock_sandbox.can_read.return_value = True

        assert validate_paths_in_sandbox(["file.txt"], ["output"], mock_sandbox) is True
        mock_sandbox.resolve.assert_called()

    def test_path_not_in_sandbox(self):
        mock_sandbox = Mock()
        mock_sandbox.resolve.side_effect = FileSandboxError("Not in sandbox")
        mock_sandbox.can_read.return_value = False

        result = validate_paths_in_sandbox(["/etc/passwd"], ["output"], mock_sandbox)
        assert result is False


class TestExecuteShell:
    """Tests for shell command execution."""

    def test_simple_command(self, tmp_path):
        result = execute_shell("echo hello", working_dir=tmp_path)
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.truncated is False

    def test_command_with_args(self, tmp_path):
        result = execute_shell("echo hello world", working_dir=tmp_path)
        assert result.exit_code == 0
        assert "hello world" in result.stdout

    def test_command_not_found(self, tmp_path):
        result = execute_shell("nonexistent_command_xyz", working_dir=tmp_path)
        assert result.exit_code == 127
        assert "not found" in result.stderr.lower()

    def test_command_with_error(self, tmp_path):
        result = execute_shell("ls nonexistent_file_xyz", working_dir=tmp_path)
        assert result.exit_code != 0
        assert result.stderr  # Should have error message

    def test_metacharacter_blocked(self, tmp_path):
        with pytest.raises(ShellBlockedError):
            execute_shell("echo hello | cat", working_dir=tmp_path)

    def test_timeout(self, tmp_path):
        # Use a very short timeout
        result = execute_shell("sleep 10", working_dir=tmp_path, timeout=1)
        assert result.exit_code == -1
        assert "timed out" in result.stderr.lower()

    def test_working_directory(self, tmp_path):
        # Create a file in tmp_path
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = execute_shell("ls", working_dir=tmp_path)
        assert result.exit_code == 0
        assert "test.txt" in result.stdout


class TestEnhanceErrorWithSandboxContext:
    """Tests for LLM-friendly error enhancement."""

    def test_success_not_modified(self):
        result = ShellResult(stdout="ok", stderr="", exit_code=0, truncated=False)
        enhanced = enhance_error_with_sandbox_context(result, None)
        assert enhanced == result

    def test_no_sandbox_not_modified(self):
        result = ShellResult(stdout="", stderr="error", exit_code=1, truncated=False)
        enhanced = enhance_error_with_sandbox_context(result, None)
        assert enhanced == result

    def test_permission_denied_enhanced(self):
        mock_sandbox = Mock()
        mock_sandbox.writable_roots = ["/sandbox/output"]

        result = ShellResult(
            stdout="",
            stderr="Permission denied: /some/path",
            exit_code=1,
            truncated=False,
        )
        enhanced = enhance_error_with_sandbox_context(result, mock_sandbox)

        assert "writable paths" in enhanced.stderr
        assert "/sandbox/output" in enhanced.stderr

    def test_network_error_enhanced(self):
        mock_sandbox = Mock()
        mock_sandbox.writable_roots = []

        result = ShellResult(
            stdout="",
            stderr="Could not resolve host: example.com",
            exit_code=1,
            truncated=False,
        )
        enhanced = enhance_error_with_sandbox_context(result, mock_sandbox)

        assert "Network access may be disabled" in enhanced.stderr


class TestShellRuleWithSandboxPaths:
    """Tests for shell rules with sandbox_paths validation."""

    def test_sandbox_paths_validation_passes(self):
        mock_sandbox = Mock()
        mock_sandbox.resolve.return_value = Path("/sandbox/output/file.txt")

        rules = [
            {
                "pattern": "cat",
                "sandbox_paths": ["output"],
                "approval_required": False,
                "allowed": True,
            }
        ]

        allowed, approval = match_shell_rules(
            "cat file.txt",
            ["cat", "file.txt"],
            rules,
            None,
            mock_sandbox,
        )
        assert allowed is True
        assert approval is False

    def test_sandbox_paths_validation_fails_tries_next_rule(self):
        mock_sandbox = Mock()
        mock_sandbox.resolve.side_effect = FileSandboxError("Not in sandbox")
        mock_sandbox.can_read.return_value = False

        rules = [
            {
                "pattern": "cat",
                "sandbox_paths": ["output"],  # Will fail validation
                "approval_required": False,
                "allowed": True,
            },
            {
                "pattern": "cat",
                "sandbox_paths": [],  # No validation
                "approval_required": True,
                "allowed": True,
            },
        ]

        allowed, approval = match_shell_rules(
            "cat /etc/passwd",
            ["cat", "/etc/passwd"],
            rules,
            None,
            mock_sandbox,
        )
        # Falls through to second rule
        assert allowed is True
        assert approval is True


class TestShellDefault:
    """Tests for shell default behavior."""

    def test_default_allow_no_approval(self):
        default = {"allowed": True, "approval_required": False}
        allowed, approval = match_shell_rules("xyz", ["xyz"], [], default, None)
        assert allowed is True
        assert approval is False

    def test_default_block(self):
        default = {"allowed": False, "approval_required": True}
        allowed, approval = match_shell_rules("xyz", ["xyz"], [], default, None)
        assert allowed is False
        assert approval is True
