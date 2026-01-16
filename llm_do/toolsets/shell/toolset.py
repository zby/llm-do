"""Shell command execution as a PydanticAI toolset with whitelist-based approval.

This module provides ShellToolset which:
1. Exposes the `shell` tool to LLMs
2. Implements whitelist-based approval via `needs_approval()` returning ApprovalResult
3. Provides custom descriptions via `get_approval_description()`
4. Delegates execution to the execution module

Whitelist model:
- Commands must match a rule OR have a default to be allowed
- No rule + no default = command is blocked

Security note: Pattern rules are UX only, not security. For kernel-level
isolation, run llm-do in a Docker container.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, cast

from pydantic import BaseModel, Field
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.toolsets.abstract import SchemaValidatorProt
from pydantic_ai_blocking_approval import (
    ApprovalConfig,
    ApprovalResult,
    needs_approval_from_config,
)

from ..validators import DictValidator
from .execution import (
    ShellBlockedError,
    check_metacharacters,
    execute_shell,
    match_shell_rules,
    parse_command,
)
from .types import ShellResult

logger = logging.getLogger(__name__)


class ShellArgs(BaseModel):
    """Arguments for shell."""

    command: str = Field(description="Command to execute (parsed with shlex)")
    timeout: int = Field(
        default=30,
        description="Timeout in seconds (default 30, max 300)",
    )


class ShellToolset(AbstractToolset[Any]):
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

    def needs_approval(
        self, name: str, tool_args: dict, ctx: Any, config: ApprovalConfig | None = None
    ) -> ApprovalResult:
        base = needs_approval_from_config(name, config)
        if base.is_blocked or base.is_pre_approved:
            return base
        if name != "shell":
            return ApprovalResult.needs_approval()

        command = tool_args.get("command", "")
        try:
            check_metacharacters(command)
            args = parse_command(command)
        except ShellBlockedError as e:
            return ApprovalResult.blocked(str(e))

        allowed, approval_required = match_shell_rules(
            command=command, args=args,
            rules=self._config.get("rules", []),
            default=self._config.get("default"),
        )
        if not allowed:
            return ApprovalResult.blocked(f"Command not in whitelist: {command}")
        return ApprovalResult.needs_approval() if approval_required else ApprovalResult.pre_approved()

    def get_approval_description(self, name: str, tool_args: dict, ctx: Any) -> str:
        if name != "shell":
            return f"{name}({tool_args})"
        command = tool_args.get("command", "")
        return f"Execute: {command[:80]}..." if len(command) > 80 else f"Execute: {command}"

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool]:
        return {
            "shell": ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name="shell",
                    description="Execute a shell command. Shell metacharacters (|, >, <, ;, &, `, $()) are blocked.",
                    parameters_json_schema=ShellArgs.model_json_schema(),
                ),
                max_retries=self._max_retries,
                args_validator=cast(SchemaValidatorProt, DictValidator(ShellArgs)),
            )
        }

    async def call_tool(
        self, name: str, tool_args: dict[str, Any], ctx: Any, tool: ToolsetTool[Any]
    ) -> ShellResult:
        timeout = min(max(tool_args.get("timeout", 30), 1), 300)
        try:
            return execute_shell(command=tool_args["command"], timeout=timeout)
        except ShellBlockedError as e:
            return ShellResult(stdout="", stderr=str(e), exit_code=1, truncated=False)
