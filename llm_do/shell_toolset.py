"""Shell command execution as a PydanticAI toolset with pattern-based approval.

This module provides ShellApprovalToolset which:
1. Exposes the `shell` tool to LLMs
2. Implements pattern-based approval via `needs_approval()`
3. Delegates execution to shell.py

Security note: Pattern rules are UX only, not security. Security comes from:
- FileSandbox for Python I/O validation
- OS sandbox (Seatbelt/bwrap) for shell subprocess enforcement (future)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import TypeAdapter
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.tools import ToolDefinition
from pydantic_ai_blocking_approval import ApprovalToolset, ApprovalMemory

from .protocols import FileSandbox
from .shell import (
    ShellBlockedError,
    execute_shell,
    enhance_error_with_sandbox_context,
    match_shell_rules,
    parse_command,
)
from .types import ShellDefault, ShellResult, ShellRule, WorkerContext

logger = logging.getLogger(__name__)


class ShellToolsetInner(AbstractToolset[WorkerContext]):
    """Core shell command execution toolset (no approval logic).

    This provides the actual shell tool implementation. Approval logic
    is handled by the ShellApprovalToolset wrapper.
    """

    def __init__(
        self,
        cwd: Optional[Path] = None,
        sandbox: Optional[FileSandbox] = None,
        id: Optional[str] = None,
        max_retries: int = 1,
    ):
        """Initialize shell toolset.

        Args:
            cwd: Working directory for shell commands. If None, uses current directory.
            sandbox: FileSandbox for enhancing error messages with context.
            id: Optional toolset ID for durable execution.
            max_retries: Maximum retries for tool calls.
        """
        self.cwd = cwd
        self.sandbox = sandbox
        self._id = id
        self._max_retries = max_retries

    @property
    def id(self) -> str | None:
        """Return toolset ID for durable execution."""
        return self._id

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

        # Determine working directory
        working_dir = self.cwd if self.cwd is not None else Path.cwd()

        try:
            result = execute_shell(
                command=command,
                working_dir=working_dir,
                timeout=timeout,
            )
            # Enhance errors with sandbox context
            return enhance_error_with_sandbox_context(result, self.sandbox)
        except ShellBlockedError as e:
            return ShellResult(
                stdout="",
                stderr=str(e),
                exit_code=1,
                truncated=False,
            )


class ShellApprovalToolset(ApprovalToolset):
    """Shell toolset with pattern-based approval.

    Wraps ShellToolsetInner with approval logic based on shell_rules
    and shell_default configuration.

    The `needs_approval()` method implements pattern matching:
    - Commands matching a rule with `allowed: false` are blocked
    - Commands matching a rule with `approval_required: false` are pre-approved
    - Other commands require approval
    """

    def __init__(
        self,
        rules: list[ShellRule],
        default: Optional[ShellDefault],
        cwd: Optional[Path],
        sandbox: Optional[FileSandbox],
        approval_callback: Callable,
        memory: Optional[ApprovalMemory] = None,
    ):
        """Initialize shell approval toolset.

        Args:
            rules: List of shell rules for pattern matching
            default: Default behavior for commands not matching any rule
            cwd: Working directory for shell commands
            sandbox: FileSandbox for path validation and error enhancement
            approval_callback: Callback for approval decisions
            memory: Optional approval memory for session caching
        """
        inner = ShellToolsetInner(cwd=cwd, sandbox=sandbox)
        super().__init__(
            inner=inner,
            approval_callback=approval_callback,
            memory=memory,
        )
        self.rules = rules
        self.default = default
        self.sandbox = sandbox

    def needs_approval(self, name: str, tool_args: dict) -> bool | dict:
        """Determine if shell command needs approval based on rules.

        Args:
            name: Tool name (should be "shell")
            tool_args: Tool arguments with "command"

        Returns:
            - False: No approval needed (pre-approved by rule)
            - dict with "description": Approval needed with custom message

        Raises:
            PermissionError: If command is blocked by rules
        """
        if name != "shell":
            # Unknown tool - require approval
            return True

        command = tool_args.get("command", "")

        # Parse command for rule matching
        try:
            args = parse_command(command)
        except ShellBlockedError:
            # Let call_tool handle the error - don't block here
            return False

        # Match against shell_rules
        allowed, approval_required = match_shell_rules(
            command=command,
            args=args,
            rules=self.rules,
            default=self.default,
            file_sandbox=self.sandbox,
        )

        # Check if command is blocked
        if not allowed:
            raise PermissionError(f"Command not allowed by shell rules: {command}")

        # Check if approval is required
        if not approval_required:
            return False  # Pre-approved

        # Approval required - return description
        truncated = command[:80] + "..." if len(command) > 80 else command
        return {"description": f"Execute: {truncated}"}
