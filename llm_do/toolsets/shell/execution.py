"""Shell command execution with whitelist-based approval.

This module provides:
- Shell command execution with subprocess
- Pattern matching for shell rules (whitelist model)
- Integration with the approval system

Security note: Pattern rules are UX only, not security. For kernel-level
isolation, run llm-do in a Docker container.
"""
from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from .types import ShellResult

logger = logging.getLogger(__name__)

# Shell metacharacters that we block (to prevent shell injection)
BLOCKED_METACHARACTERS = frozenset(['|', '>', '<', ';', '&', '`', '$(', '${'])

# Maximum output size in bytes (50KB)
MAX_OUTPUT_BYTES = 50 * 1024

# Default timeout in seconds
DEFAULT_TIMEOUT = 30


class ShellError(Exception):
    """Base error for shell execution failures."""
    pass


class ShellBlockedError(ShellError):
    """Raised when a command is blocked by rules or metacharacters."""
    pass


def check_metacharacters(command: str) -> None:
    """Check for blocked shell metacharacters.

    Args:
        command: Raw command string

    Raises:
        ShellBlockedError: If command contains blocked metacharacters
    """
    for char in BLOCKED_METACHARACTERS:
        if char in command:
            raise ShellBlockedError(
                f"Command contains blocked metacharacter '{char}'. "
                f"Shell metacharacters are not allowed for security reasons."
            )


def parse_command(command: str) -> List[str]:
    """Parse command string into arguments using shlex.

    Args:
        command: Command string to parse

    Returns:
        List of command arguments

    Raises:
        ShellBlockedError: If command cannot be parsed
    """
    try:
        return shlex.split(command)
    except ValueError as e:
        raise ShellBlockedError(f"Cannot parse command: {e}")


def _pattern_matches_args(pattern: str, args: List[str]) -> bool:
    """Check if parsed args match a shell pattern.

    Pattern matching uses tokenized comparison to avoid overmatching:
    - Pattern "git" matches ["git"], ["git", "status"], but NOT ["gitx"]
    - Pattern "git status" matches ["git", "status"], ["git", "status", "-s"]

    Args:
        pattern: Shell pattern string (will be tokenized)
        args: Parsed command arguments

    Returns:
        True if args start with the pattern tokens (exact token match)
    """
    if not pattern or not args:
        return False

    try:
        pattern_tokens = shlex.split(pattern)
    except ValueError:
        # If pattern can't be parsed, fall back to prefix match on first arg
        return args[0] == pattern or args[0].startswith(pattern + " ")

    if len(args) < len(pattern_tokens):
        return False

    # Each pattern token must match exactly
    return args[:len(pattern_tokens)] == pattern_tokens


def _rule_requires_approval(rule: dict, args: List[str]) -> bool:
    """Determine approval requirement for a matched rule."""
    approval_required = rule.get("approval_required", True)
    required_if_args = rule.get("approval_required_if_args")
    if required_if_args:
        if isinstance(required_if_args, (list, tuple, set)):
            flags = [str(item) for item in required_if_args]
        else:
            flags = [str(required_if_args)]
        if any(flag in args for flag in flags):
            return True
    return approval_required


def match_shell_rules(
    command: str,
    args: List[str],
    rules: List[dict],
    default: Optional[dict],
) -> Tuple[bool, bool]:
    """Match command against shell rules (whitelist model).

    Whitelist semantics:
    - Rule in config → command is allowed (with rule's approval_required)
    - No rule but default exists → allowed (with default's approval_required)
    - No rule and no default → BLOCKED

    Args:
        command: Original command string (unused, kept for API compatibility)
        args: Parsed command arguments
        rules: List of shell rule dicts with keys: pattern, approval_required,
            approval_required_if_args (optional)
        default: Default behavior dict with key: approval_required (presence = allow unmatched)

    Returns:
        Tuple of (allowed, approval_required)
    """
    for rule in rules:
        pattern = rule.get("pattern", "")
        if _pattern_matches_args(pattern, args):
            logger.debug(f"Command args {args} match rule pattern '{pattern}'")
            # Rule matched → allowed with rule's approval setting
            return (True, _rule_requires_approval(rule, args))

    # No rule matched - check for default
    if default is not None:
        # Default exists → allow with default's approval setting
        return (True, default.get("approval_required", True))

    # No rule and no default → blocked (whitelist model)
    return (False, True)


def execute_shell(
    command: str,
    working_dir: Optional[Path] = None,
    timeout: int = DEFAULT_TIMEOUT,
    env: Optional[dict] = None,
) -> ShellResult:
    """Execute a shell command and return the result.

    Args:
        command: Command string to execute
        working_dir: Working directory for the command (defaults to cwd)
        timeout: Timeout in seconds
        env: Environment variables (defaults to current environment)

    Returns:
        ShellResult with stdout, stderr, exit_code, and truncated flag

    Raises:
        ShellBlockedError: If command cannot be parsed
        ShellError: If command execution fails

    Note:
        Metacharacter blocking is handled by the approval layer (ShellToolset.needs_approval).
    """
    # Parse command
    args = parse_command(command)
    if not args:
        raise ShellBlockedError("Empty command")

    logger.info(f"Executing shell command: {args}")

    try:
        result = subprocess.run(
            args,
            cwd=working_dir,
            capture_output=True,
            timeout=timeout,
            env=env,
            # Don't use shell=True for security
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return ShellResult(
            stdout="",
            stderr=f"Command timed out after {timeout} seconds",
            exit_code=-1,
            truncated=False,
        )
    except FileNotFoundError:
        return ShellResult(
            stdout="",
            stderr=f"Command not found: {args[0]}",
            exit_code=127,
            truncated=False,
        )
    except PermissionError:
        return ShellResult(
            stdout="",
            stderr=f"Permission denied: {args[0]}",
            exit_code=126,
            truncated=False,
        )
    except Exception as e:
        raise ShellError(f"Failed to execute command: {e}")

    # Decode output
    try:
        stdout = result.stdout.decode('utf-8', errors='replace')
    except Exception:
        stdout = str(result.stdout)

    try:
        stderr = result.stderr.decode('utf-8', errors='replace')
    except Exception:
        stderr = str(result.stderr)

    # Check if truncation needed
    truncated = False
    if len(stdout) > MAX_OUTPUT_BYTES:
        stdout = stdout[:MAX_OUTPUT_BYTES] + "\n... (output truncated)"
        truncated = True
    if len(stderr) > MAX_OUTPUT_BYTES:
        stderr = stderr[:MAX_OUTPUT_BYTES] + "\n... (output truncated)"
        truncated = True

    return ShellResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=result.returncode,
        truncated=truncated,
    )
