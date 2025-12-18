"""Shell toolset package.

This package provides shell command execution with whitelist-based approval.

Whitelist model:
- Commands must match a rule OR have a default to be allowed
- No rule + no default = command is blocked

For kernel-level isolation, run llm-do in a Docker container.
"""
from __future__ import annotations

from .execution import (
    BLOCKED_METACHARACTERS,
    MAX_OUTPUT_BYTES,
    ShellBlockedError,
    ShellError,
    check_metacharacters,
    execute_shell,
    match_shell_rules,
    parse_command,
)
from .types import ShellDefault, ShellResult, ShellRule

# Note: ShellToolset is imported separately to avoid circular imports
# Use: from llm_do.shell.toolset import ShellToolset

__all__ = [
    # Constants
    "BLOCKED_METACHARACTERS",
    "MAX_OUTPUT_BYTES",
    # Types
    "ShellDefault",
    "ShellResult",
    "ShellRule",
    # Errors
    "ShellBlockedError",
    "ShellError",
    # Execution
    "check_metacharacters",
    "execute_shell",
    "match_shell_rules",
    "parse_command",
]


def __getattr__(name: str):
    """Lazy import for ShellToolset to avoid circular imports."""
    if name == "ShellToolset":
        from .toolset import ShellToolset
        return ShellToolset
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
