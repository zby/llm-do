"""Worker delegation as a PydanticAI toolset with approval.

This module provides DelegationApprovalToolset which:
1. Exposes worker_call and worker_create tools to LLMs
2. Implements approval logic via `needs_approval()`
3. Enforces allow_workers restrictions
"""
from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional

from pydantic import TypeAdapter
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.tools import ToolDefinition
from pydantic_ai_blocking_approval import ApprovalToolset, ApprovalMemory

from .protocols import WorkerCreator, WorkerDelegator
from .types import WorkerContext

logger = logging.getLogger(__name__)


class DelegationToolsetInner(AbstractToolset[WorkerContext]):
    """Core worker delegation toolset (no approval logic).

    This provides the actual worker_call and worker_create tool implementations.
    Approval logic is handled by the DelegationApprovalToolset wrapper.
    """

    def __init__(
        self,
        delegator: WorkerDelegator,
        creator: WorkerCreator,
        id: Optional[str] = None,
        max_retries: int = 1,
    ):
        """Initialize delegation toolset.

        Args:
            delegator: Implementation of worker delegation (DI)
            creator: Implementation of worker creation (DI)
            id: Optional toolset ID for durable execution.
            max_retries: Maximum retries for tool calls.
        """
        self.delegator = delegator
        self.creator = creator
        self._id = id
        self._max_retries = max_retries

    @property
    def id(self) -> str | None:
        """Return toolset ID for durable execution."""
        return self._id

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool]:
        """Return the worker_call and worker_create tool definitions."""
        worker_call_schema = {
            "type": "object",
            "properties": {
                "worker": {
                    "type": "string",
                    "description": "Name of the worker to delegate to",
                },
                "input_data": {
                    "description": "Input data to pass to the worker",
                },
                "attachments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of file paths to attach",
                },
            },
            "required": ["worker"],
        }

        worker_create_schema = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name for the new worker",
                },
                "instructions": {
                    "type": "string",
                    "description": "System prompt/instructions for the worker",
                },
                "description": {
                    "type": "string",
                    "description": "Optional description of what the worker does",
                },
                "model": {
                    "type": "string",
                    "description": "Optional model to use (e.g., 'anthropic:claude-sonnet-4')",
                },
                "output_schema_ref": {
                    "type": "string",
                    "description": "Optional reference to output schema",
                },
                "force": {
                    "type": "boolean",
                    "description": "Overwrite existing worker if true",
                    "default": False,
                },
            },
            "required": ["name", "instructions"],
        }

        return {
            "worker_call": ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name="worker_call",
                    description="Delegate to another registered worker",
                    parameters_json_schema=worker_call_schema,
                ),
                max_retries=self._max_retries,
                args_validator=TypeAdapter(dict[str, Any]).validator,
            ),
            "worker_create": ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name="worker_create",
                    description="Persist a new worker definition using the active profile",
                    parameters_json_schema=worker_create_schema,
                ),
                max_retries=self._max_retries,
                args_validator=TypeAdapter(dict[str, Any]).validator,
            ),
        }

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[Any],
    ) -> Any:
        """Execute a delegation tool.

        Args:
            name: Tool name ("worker_call" or "worker_create")
            tool_args: Tool arguments
            ctx: Run context (unused here, approval already handled by wrapper)
            tool: Tool definition

        Returns:
            Result from the delegated worker or creation status
        """
        if name == "worker_call":
            worker = tool_args["worker"]
            input_data = tool_args.get("input_data")
            attachments = tool_args.get("attachments")
            return await self.delegator.call_async(worker, input_data, attachments)

        elif name == "worker_create":
            return self.creator.create(
                name=tool_args["name"],
                instructions=tool_args["instructions"],
                description=tool_args.get("description"),
                model=tool_args.get("model"),
                output_schema_ref=tool_args.get("output_schema_ref"),
                force=tool_args.get("force", False),
            )

        else:
            raise ValueError(f"Unknown delegation tool: {name}")


class DelegationApprovalToolset(ApprovalToolset):
    """Delegation toolset with approval.

    Wraps DelegationToolsetInner with approval logic:
    - worker_call: Blocked if target not in allow_workers, otherwise requires approval
    - worker_create: Always requires approval (creates new workers)
    """

    def __init__(
        self,
        config: dict,
        delegator: WorkerDelegator,
        creator: WorkerCreator,
        approval_callback: Callable,
        memory: Optional[ApprovalMemory] = None,
    ):
        """Initialize delegation approval toolset.

        Args:
            config: Delegation toolset configuration dict (allow_workers)
            delegator: Implementation of worker delegation (DI)
            creator: Implementation of worker creation (DI)
            approval_callback: Callback for approval decisions
            memory: Optional approval memory for session caching
        """
        inner = DelegationToolsetInner(delegator=delegator, creator=creator)
        super().__init__(
            inner=inner,
            approval_callback=approval_callback,
            memory=memory,
            config=config,
        )

    def needs_approval(self, name: str, tool_args: dict) -> bool | dict:
        """Determine if delegation tool needs approval.

        Args:
            name: Tool name ("worker_call" or "worker_create")
            tool_args: Tool arguments

        Returns:
            - False: No approval needed (pre-approved)
            - dict with "description": Approval needed with custom message

        Raises:
            PermissionError: If worker_call targets a worker not in allow_workers
        """
        if name == "worker_call":
            target_worker = tool_args.get("worker", "")

            # Check if target worker is allowed
            # allow_workers=[] means no delegation allowed
            # allow_workers=['*'] means all workers allowed
            # allow_workers=['foo', 'bar'] means only specific workers allowed
            allow_workers = self.config.get("allow_workers", [])
            if '*' not in allow_workers and target_worker not in allow_workers:
                raise PermissionError(
                    f"Worker '{target_worker}' not in allow_workers list. "
                    f"Allowed: {allow_workers}"
                )

            # Worker call always requires approval
            return {"description": f"Delegate to worker: {target_worker}"}

        elif name == "worker_create":
            worker_name = tool_args.get("name", "")
            # Worker creation always requires approval
            return {"description": f"Create new worker: {worker_name}"}

        # Unknown tool - require approval
        return True
