"""Shell command execution with whitelist-based approval.

This module provides:
- Shell command execution with subprocess
- Pattern matching for shell rules (whitelist model)
- Path validation using FileSandbox
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

from pydantic_ai_filesystem_sandbox import SandboxError

from ..protocols import FileSandbox
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


def extract_path_arguments(args: List[str]) -> List[str]:
    """Extract potential file path arguments from command.

    Heuristic: non-flag arguments that don't start with '-' are potential paths.

    Args:
        args: Command arguments (first element is the command itself)

    Returns:
        List of potential path arguments
    """
    paths = []
    # Skip the command itself (args[0])
    for arg in args[1:]:
        # Skip flags
        if arg.startswith('-'):
            continue
        # Skip empty args
        if not arg:
            continue
        # Everything else might be a path
        paths.append(arg)
    return paths


def validate_paths_in_sandbox(
    paths: List[str],
    allowed_sandboxes: List[str],
    file_sandbox: FileSandbox,
) -> bool:
    """Validate that all paths are within allowed sandboxes.

    Args:
        paths: List of path arguments to validate
        allowed_sandboxes: List of sandbox names that are allowed
        file_sandbox: FileSandbox instance for path resolution

    Returns:
        True if all paths are valid, False otherwise
    """
    if not paths:
        return True

    if not allowed_sandboxes:
        return True

    for path in paths:
        # Try to resolve the path - check if it's in any allowed sandbox
        found_in_allowed = False
        for sandbox_name in allowed_sandboxes:
            try:
                # Try sandbox_name/path format
                file_sandbox.resolve(f"{sandbox_name}/{path}")
                found_in_allowed = True
                break
            except SandboxError:
                continue

        if not found_in_allowed:
            # Also try the path directly in case it already includes sandbox name
            try:
                resolved = file_sandbox.resolve(path)
                # Check if it's in any of the allowed sandboxes
                for sandbox_name in allowed_sandboxes:
                    if file_sandbox.can_read(f"{sandbox_name}/{path}"):
                        found_in_allowed = True
                        break
            except SandboxError:
                pass

        if not found_in_allowed:
            logger.debug(f"Path '{path}' not in allowed sandboxes: {allowed_sandboxes}")
            return False

    return True


def match_shell_rules(
    command: str,
    args: List[str],
    rules: List[dict],
    default: Optional[dict],
    file_sandbox: Optional[FileSandbox],
) -> Tuple[bool, bool]:
    """Match command against shell rules (whitelist model).

    Whitelist semantics:
    - Rule in config → command is allowed (with rule's approval_required)
    - No rule but default exists → allowed (with default's approval_required)
    - No rule and no default → BLOCKED

    Args:
        command: Original command string
        args: Parsed command arguments
        rules: List of shell rule dicts with keys: pattern, sandbox_paths, approval_required
        default: Default behavior dict with key: approval_required (presence = allow unmatched)
        file_sandbox: FileSandbox for path validation (optional)

    Returns:
        Tuple of (allowed, approval_required)
    """
    for rule in rules:
        pattern = rule.get("pattern", "")
        # Simple prefix match
        if command.startswith(pattern) or command == pattern:
            logger.debug(f"Command '{command}' matches rule pattern '{pattern}'")

            # If rule has sandbox_paths, validate path arguments
            sandbox_paths = rule.get("sandbox_paths", [])
            if sandbox_paths and file_sandbox is not None:
                path_args = extract_path_arguments(args)
                if not validate_paths_in_sandbox(path_args, sandbox_paths, file_sandbox):
                    logger.debug(f"Path validation failed for rule '{pattern}'")
                    continue  # Try next rule

            # Rule matched → allowed with rule's approval setting
            return (True, rule.get("approval_required", True))

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
        ShellBlockedError: If command contains blocked metacharacters
        ShellError: If command execution fails
    """
    # Check for blocked metacharacters
    check_metacharacters(command)

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


def enhance_error_with_sandbox_context(
    result: ShellResult,
    file_sandbox: Optional[FileSandbox],
) -> ShellResult:
    """Add sandbox context to error messages to help the LLM.

    Args:
        result: Original shell result
        file_sandbox: FileSandbox for context

    Returns:
        ShellResult with enhanced error messages
    """
    if result.exit_code == 0 or file_sandbox is None:
        return result

    stderr = result.stderr

    # Enhance "Permission denied" errors
    if "Permission denied" in stderr or "permission denied" in stderr:
        writable = file_sandbox.writable_roots
        if writable:
            stderr += f"\n\nNote: This worker's writable paths are: {', '.join(writable)}"
        else:
            stderr += "\n\nNote: This worker has no writable paths configured."

    # Enhance "Network unreachable" errors
    if "Network is unreachable" in stderr or "Could not resolve host" in stderr:
        stderr += "\n\nNote: Network access may be disabled for this worker."

    return ShellResult(
        stdout=result.stdout,
        stderr=stderr,
        exit_code=result.exit_code,
        truncated=result.truncated,
    )
