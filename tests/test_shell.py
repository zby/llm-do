"""Tests for shell command execution and pattern matching."""
from __future__ import annotations

import pytest

from llm_do.shell import (
    ShellBlockedError,
    check_metacharacters,
    execute_shell,
    match_shell_rules,
    parse_command,
)


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


class TestMatchShellRules:
    """Tests for shell rule pattern matching."""

    def test_exact_match(self):
        rules = [{"pattern": "git status", "approval_required": False, "allowed": True}]
        allowed, approval = match_shell_rules("git status", ["git", "status"], rules, None)
        assert allowed is True
        assert approval is False

    def test_prefix_match(self):
        rules = [{"pattern": "git", "approval_required": False, "allowed": True}]
        allowed, approval = match_shell_rules("git status", ["git", "status"], rules, None)
        assert allowed is True
        assert approval is False

    def test_no_match_uses_default(self):
        rules = [{"pattern": "git", "approval_required": False}]
        default = {"approval_required": True}
        allowed, approval = match_shell_rules("ls -la", ["ls", "-la"], rules, default)
        assert allowed is True  # Default exists
        assert approval is True

    def test_no_match_no_default_blocks(self):
        """Whitelist model: no matching rule + no default = blocked."""
        rules = [{"pattern": "git", "approval_required": False}]
        allowed, approval = match_shell_rules("ls -la", ["ls", "-la"], rules, None)
        assert allowed is False  # Whitelist blocks unmatched commands
        assert approval is True

    def test_first_match_wins(self):
        rules = [
            {"pattern": "git status", "approval_required": False},
            {"pattern": "git", "approval_required": True},
        ]
        allowed, approval = match_shell_rules("git status", ["git", "status"], rules, None)
        assert allowed is True  # Matched first rule
        assert approval is False  # First rule wins

    def test_rule_match_means_allowed(self):
        """Whitelist model: presence in rules = allowed."""
        rules = [{"pattern": "rm", "approval_required": True}]
        allowed, approval = match_shell_rules("rm -rf /", ["rm", "-rf", "/"], rules, None)
        assert allowed is True  # In rules = allowed
        assert approval is True




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






class TestShellDefault:
    """Tests for shell default behavior (whitelist model)."""

    def test_default_allows_unmatched(self):
        """Presence of default = unmatched commands are allowed."""
        default = {"approval_required": False}
        allowed, approval = match_shell_rules("xyz", ["xyz"], [], default)
        assert allowed is True  # Default exists = allowed
        assert approval is False

    def test_no_default_blocks_unmatched(self):
        """Absence of default = unmatched commands are blocked."""
        allowed, approval = match_shell_rules("xyz", ["xyz"], [], None)
        assert allowed is False  # No default = blocked
        assert approval is True


class TestShellToolsetNeedsApproval:
    """Tests for ShellToolset.needs_approval metacharacter blocking."""

    def test_metacharacter_blocked_in_needs_approval(self):
        """Metacharacters are blocked at the approval layer."""
        from llm_do.toolsets.shell import ShellToolset

        toolset = ShellToolset(config={"default": {"approval_required": False}})
        result = toolset.needs_approval(
            "shell",
            {"command": "echo hello | cat"},
            None,
            None,
        )
        assert result.is_blocked
        assert "blocked metacharacter" in result.block_reason.lower()

    def test_clean_command_not_blocked(self):
        """Clean commands pass metacharacter check."""
        from llm_do.toolsets.shell import ShellToolset

        toolset = ShellToolset(config={"default": {"approval_required": False}})
        result = toolset.needs_approval(
            "shell",
            {"command": "ls -la /tmp"},
            None,
            None,
        )
        assert not result.is_blocked
        assert result.is_pre_approved
