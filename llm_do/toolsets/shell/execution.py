"""Shell command execution with whitelist-based approval."""
from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from .types import ShellResult

logger = logging.getLogger(__name__)
BLOCKED_METACHARACTERS = frozenset(['|', '>', '<', ';', '&', '`', '$(', '${'])
MAX_OUTPUT_BYTES = 50 * 1024
DEFAULT_TIMEOUT = 30


class ShellError(Exception):
    pass


class ShellBlockedError(ShellError):
    pass


def check_metacharacters(command: str) -> None:
    for char in BLOCKED_METACHARACTERS:
        if char in command:
            raise ShellBlockedError(f"Command contains blocked metacharacter '{char}'.")


def parse_command(command: str) -> List[str]:
    try:
        return shlex.split(command)
    except ValueError as e:
        raise ShellBlockedError(f"Cannot parse command: {e}")


def _pattern_matches_args(pattern: str, args: List[str]) -> bool:
    if not pattern or not args:
        return False
    try:
        pattern_tokens = shlex.split(pattern)
    except ValueError:
        return args[0] == pattern or args[0].startswith(pattern + " ")
    return len(args) >= len(pattern_tokens) and args[:len(pattern_tokens)] == pattern_tokens


def _rule_requires_approval(rule: dict, args: List[str]) -> bool:
    required_if_args = rule.get("approval_required_if_args")
    if required_if_args:
        flags = [str(item) for item in required_if_args] if isinstance(required_if_args, (list, tuple, set)) else [str(required_if_args)]
        if any(flag in args for flag in flags):
            return True
    return rule.get("approval_required", True)


def match_shell_rules(command: str, args: List[str], rules: List[dict], default: Optional[dict]) -> Tuple[bool, bool]:
    for rule in rules:
        if _pattern_matches_args(rule.get("pattern", ""), args):
            return (True, _rule_requires_approval(rule, args))
    if default is not None:
        return (True, default.get("approval_required", True))
    return (False, True)


def _decode_output(data: bytes) -> str:
    try:
        return data.decode('utf-8', errors='replace')
    except Exception:
        return str(data)


def _truncate_output(text: str) -> tuple[str, bool]:
    if len(text) > MAX_OUTPUT_BYTES:
        return text[:MAX_OUTPUT_BYTES] + "\n... (output truncated)", True
    return text, False


def execute_shell(
    command: str, working_dir: Optional[Path] = None, timeout: int = DEFAULT_TIMEOUT, env: Optional[dict] = None
) -> ShellResult:
    args = parse_command(command)
    if not args:
        raise ShellBlockedError("Empty command")
    logger.info(f"Executing shell command: {args}")

    try:
        result = subprocess.run(args, cwd=working_dir, capture_output=True, timeout=timeout, env=env, shell=False)
    except subprocess.TimeoutExpired:
        return ShellResult(stdout="", stderr=f"Command timed out after {timeout} seconds", exit_code=-1, truncated=False)
    except FileNotFoundError:
        return ShellResult(stdout="", stderr=f"Command not found: {args[0]}", exit_code=127, truncated=False)
    except PermissionError:
        return ShellResult(stdout="", stderr=f"Permission denied: {args[0]}", exit_code=126, truncated=False)
    except Exception as e:
        raise ShellError(f"Failed to execute command: {e}")

    stdout, trunc1 = _truncate_output(_decode_output(result.stdout))
    stderr, trunc2 = _truncate_output(_decode_output(result.stderr))
    return ShellResult(stdout=stdout, stderr=stderr, exit_code=result.returncode, truncated=trunc1 or trunc2)
