"""Worker delegation as a PydanticAI toolset with approval.

This module provides DelegationToolset which:
1. Exposes worker_call and worker_create tools to LLMs
2. Implements approval logic via `needs_approval()`
3. Enforces allow_workers restrictions

Delegation and creation logic is implemented directly in this module,
importing from runtime.py (no circular dependency since types.py doesn't
import from runtime.py).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import TypeAdapter
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.tools import ToolDefinition

from .sandbox import AttachmentPayload
from .types import WorkerContext, WorkerSpec

logger = logging.getLogger(__name__)


class DelegationToolset(AbstractToolset[WorkerContext]):
    """Worker delegation toolset with approval.

    This toolset exposes worker_call and worker_create tools to LLMs.
    The `needs_approval()` method is called by ApprovalToolset wrapper
    to determine if a delegation needs user approval.

    Approval logic:
    - worker_call: Blocked if target not in allow_workers, otherwise requires approval
    - worker_create: Always requires approval (creates new workers)
    """

    def __init__(
        self,
        config: dict,
        id: Optional[str] = None,
        max_retries: int = 1,
    ):
        """Initialize delegation toolset.

        Args:
            config: Delegation toolset configuration dict (allow_workers)
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

    def needs_approval(self, name: str, tool_args: dict, ctx: Any) -> bool | dict:
        """Determine if delegation tool needs approval.

        Args:
            name: Tool name ("worker_call" or "worker_create")
            tool_args: Tool arguments
            ctx: RunContext with deps

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
            allow_workers = self._config.get("allow_workers", [])
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

    def _check_approval(
        self,
        ctx: WorkerContext,
        tool_name: str,
        payload: Dict[str, Any],
        description: str,
    ) -> None:
        """Check approval using the unified ApprovalController.

        Raises PermissionError if approval is denied.
        """
        from pydantic_ai_blocking_approval import ApprovalRequest

        request = ApprovalRequest(
            tool_name=tool_name,
            description=description,
            tool_args=payload,
        )
        decision = ctx.approval_controller.request_approval_sync(request)
        if not decision.approved:
            note = f": {decision.note}" if decision.note else ""
            raise PermissionError(f"Approval denied for {tool_name}{note}")

    def _prepare_attachments(
        self,
        ctx: WorkerContext,
        worker: str,
        attachments: Optional[List[str]],
    ) -> Optional[List[AttachmentPayload]]:
        """Validate attachments and check sandbox.read approvals.

        Returns attachment payloads ready for call_worker_async.

        Note: This does NOT check worker.call approval - that's handled by
        ApprovalToolset via needs_approval(). Only sandbox.read for attachments.
        """
        if not attachments:
            return None

        resolved_attachments, attachment_metadata = ctx.validate_attachments(attachments)

        # Check sandbox.read approval for each attachment before sharing
        for meta in attachment_metadata:
            self._check_approval(
                ctx,
                "sandbox.read",
                {"path": f"{meta['sandbox']}/{meta['path']}", "bytes": meta["bytes"], "target_worker": worker},
                f"Share file '{meta['sandbox']}/{meta['path']}' with worker '{worker}'",
            )

        attachment_payloads = [
            AttachmentPayload(
                path=path,
                display_name=f"{meta['sandbox']}/{meta['path']}",
            )
            for path, meta in zip(resolved_attachments, attachment_metadata)
        ]

        return attachment_payloads

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
            ctx: Run context with WorkerContext as deps
            tool: Tool definition

        Returns:
            Result from the delegated worker or creation status
        """
        # Import here to avoid circular dependency (types.py doesn't import runtime)
        from .runtime import call_worker_async, create_worker

        worker_ctx: WorkerContext = ctx.deps

        if name == "worker_call":
            worker = tool_args["worker"]
            input_data = tool_args.get("input_data")
            attachments = tool_args.get("attachments")

            # Validate attachments and check sandbox.read approvals
            # (worker.call approval already handled by ApprovalToolset)
            attachment_payloads = self._prepare_attachments(worker_ctx, worker, attachments)

            result = await call_worker_async(
                registry=worker_ctx.registry,
                worker=worker,
                input_data=input_data,
                caller_context=worker_ctx,
                attachments=attachment_payloads,
            )
            return result.output

        elif name == "worker_create":
            # (worker.create approval already handled by ApprovalToolset)
            spec = WorkerSpec(
                name=tool_args["name"],
                instructions=tool_args["instructions"],
                description=tool_args.get("description"),
                model=tool_args.get("model"),
                output_schema_ref=tool_args.get("output_schema_ref"),
            )
            created = create_worker(
                registry=worker_ctx.registry,
                spec=spec,
                defaults=worker_ctx.creation_defaults,
                force=tool_args.get("force", False),
            )
            return created.model_dump(mode="json")

        else:
            raise ValueError(f"Unknown delegation tool: {name}")
