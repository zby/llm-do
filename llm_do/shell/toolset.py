"""Shell command execution as a PydanticAI toolset with whitelist-based approval.

This module provides ShellToolset which:
1. Exposes the `shell` tool to LLMs
2. Implements whitelist-based approval via `needs_approval()` returning ApprovalResult
3. Provides custom descriptions via `get_approval_description()`
4. Delegates execution to shell.py

Whitelist model:
- Commands must match a rule OR have a default to be allowed
- No rule + no default = command is blocked

Security note: Pattern rules are UX only, not security. For kernel-level
isolation, run llm-do in a Docker container.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from pydantic import TypeAdapter
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.tools import ToolDefinition
from pydantic_ai_blocking_approval import ApprovalResult

from ..protocols import FileSandbox
from ..types import WorkerContext
from .execution import (
    ShellBlockedError,
    execute_shell,
    enhance_error_with_sandbox_context,
    match_shell_rules,
    parse_command,
)
from .types import ShellResult

logger = logging.getLogger(__name__)


class ShellToolset(AbstractToolset[WorkerContext]):
    """Shell command execution toolset with pattern-based approval (whitelist model).

    This toolset exposes the `shell` tool to LLMs and implements approval
    logic based on shell configuration rules. The `needs_approval()` method
    is called by ApprovalToolset wrapper to determine if a command needs
    user approval.

    Whitelist semantics:
    - Command matches a rule → allowed (with rule's approval_required setting)
    - No rule matches but default exists → allowed (with default's approval_required)
    - No rule matches and no default → BLOCKED (ApprovalResult.blocked)
    """

    def __init__(
        self,
        config: dict,
        id: Optional[str] = None,
        max_retries: int = 1,
    ):
        """Initialize shell toolset.

        Args:
            config: Shell toolset configuration dict (rules, default)
            id: Optional toolset ID for durable execution.
            max_retries: Maximum retries for tool calls.
        """
        self._config = config
        self._id = id
        self._max_retries = max_retries

    @property
    def id(self) -> str | None:
        """Return toolset ID for durable execution."""
        return self._id

    @property
    def config(self) -> dict:
        """Return the toolset configuration."""
        return self._config

    def _get_sandbox(self, ctx: Any) -> Optional[FileSandbox]:
        """Get sandbox from ctx.deps (WorkerContext)."""
        if ctx is not None and hasattr(ctx, "deps") and ctx.deps is not None:
            return getattr(ctx.deps, "sandbox", None)
        return None

    def needs_approval(self, name: str, tool_args: dict, ctx: Any) -> ApprovalResult:
        """Determine if shell command needs approval based on whitelist rules.

        Args:
            name: Tool name (should be "shell")
            tool_args: Tool arguments with "command"
            ctx: RunContext with deps

        Returns:
            ApprovalResult with status: blocked, pre_approved, or needs_approval
        """
        if name != "shell":
            # Unknown tool - require approval
            return ApprovalResult.needs_approval()

        command = tool_args.get("command", "")

        # Parse command for rule matching
        try:
            args = parse_command(command)
        except ShellBlockedError:
            # Let call_tool handle the error - don't block here
            # (ShellBlockedError is for shell metacharacters like |, >, etc.)
            return ApprovalResult.pre_approved()

        # Match against shell rules from config
        allowed, approval_required = match_shell_rules(
            command=command,
            args=args,
            rules=self._config.get("rules", []),
            default=self._config.get("default"),
            file_sandbox=self._get_sandbox(ctx),
        )

        # Check if command is in whitelist
        if not allowed:
            return ApprovalResult.blocked(
                f"Command not in whitelist (no matching rule and no default): {command}"
            )

        # Check if approval is required
        if not approval_required:
            return ApprovalResult.pre_approved()

        # Approval required
        return ApprovalResult.needs_approval()

    def get_approval_description(self, name: str, tool_args: dict, ctx: Any) -> str:
        """Return human-readable description for approval prompt.

        Args:
            name: Tool name (should be "shell")
            tool_args: Tool arguments with "command"
            ctx: RunContext with deps

        Returns:
            Description string to show user
        """
        if name != "shell":
            return f"{name}({tool_args})"

        command = tool_args.get("command", "")
        truncated = command[:80] + "..." if len(command) > 80 else command
        return f"Execute: {truncated}"

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool]:
        """Return the shell tool definition."""
        shell_schema = {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to execute (parsed with shlex)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 30, max 300)",
                    "default": 30,
                },
            },
            "required": ["command"],
        }

        return {
            "shell": ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name="shell",
                    description=(
                        "Execute a shell command. Commands are parsed with shlex and "
                        "executed without a shell for security. Shell metacharacters "
                        "(|, >, <, ;, &, `, $()) are blocked."
                    ),
                    parameters_json_schema=shell_schema,
                ),
                max_retries=self._max_retries,
                args_validator=TypeAdapter(dict[str, Any]).validator,
            )
        }

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[Any],
    ) -> ShellResult:
        """Execute a shell command.

        Args:
            name: Tool name (should be "shell")
            tool_args: Tool arguments with "command" and optional "timeout"
            ctx: Run context (unused here, approval already handled by wrapper)
            tool: Tool definition

        Returns:
            ShellResult with stdout, stderr, exit_code, and truncated flag
        """
        command = tool_args["command"]
        timeout = tool_args.get("timeout", 30)

        # Enforce timeout limits
        timeout = min(max(timeout, 1), 300)

        try:
            result = execute_shell(
                command=command,
                timeout=timeout,
            )
            # Enhance errors with sandbox context
            return enhance_error_with_sandbox_context(result, self._get_sandbox(ctx))
        except ShellBlockedError as e:
            return ShellResult(
                stdout="",
                stderr=str(e),
                exit_code=1,
                truncated=False,
            )
