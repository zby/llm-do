"""Shell-related type definitions.

This module contains the data models used by the shell toolset:
- ShellResult: Output from shell command execution
- ShellRule: Pattern-based approval rules
- ShellDefault: Default behavior for unmatched commands
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ShellResult(BaseModel):
    """Result from a shell command execution."""

    stdout: str
    stderr: str
    exit_code: int
    truncated: bool = False  # True if output exceeded limit


class ShellRule(BaseModel):
    """Pattern-based rule for shell command approval.

    Rules are matched in order. First match wins.
    Presence in rules = command is allowed (whitelist model).
    """

    pattern: str = Field(description="Command prefix to match (e.g., 'git status')")
    approval_required: bool = Field(
        default=True,
        description="Whether this command requires user approval"
    )


class ShellDefault(BaseModel):
    """Default behavior for shell commands that don't match any rule.

    Whitelist model:
    - Presence of a default section = unmatched commands are allowed
    - Absence of default = unmatched commands are BLOCKED
    """

    approval_required: bool = Field(
        default=True,
        description="Whether unmatched commands require approval"
    )


__all__ = [
    "ShellDefault",
    "ShellResult",
    "ShellRule",
]
