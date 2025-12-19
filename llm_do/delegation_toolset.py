"""Delegation toolset - workers exposed as direct tools to LLMs.

This module provides DelegationToolset which:
1. Exposes configured workers as direct tools (e.g., `_worker_summarizer(input=...)`)
2. Optionally exposes worker_create and worker_call tools when configured
3. Implements approval logic via `needs_approval()` returning ApprovalResult
4. Provides custom descriptions via `get_approval_description()`

This replaces the old worker_call indirection with direct tool invocation:
- Before: `worker_call(worker="summarizer", input_data="...")`
- After: `_worker_summarizer(input="...", attachments=[...])`

Tool schema is dynamic:
- All worker tools have `input: str` (required)
- If worker accepts attachments (attachment_policy.max_attachments > 0),
  adds optional `attachments: list[str]` parameter
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import TypeAdapter
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.tools import ToolDefinition
from pydantic_ai_blocking_approval import ApprovalResult

from .attachments import AttachmentPayload
from .types import WorkerContext, WorkerSpec

logger = logging.getLogger(__name__)

# Prefix for worker tools to identify them in call_tool
_WORKER_TOOL_PREFIX = "_worker_"
_RESERVED_TOOLS = {"worker_call", "worker_create"}


class DelegationToolset(AbstractToolset[WorkerContext]):
    """Delegation toolset - workers exposed as direct tools.

    Each configured worker is exposed as a tool with the worker's name.
    The `needs_approval()` method is called by ApprovalToolset wrapper
    to determine if a delegation needs user approval.

    Approval logic:
    - Worker tools (worker names): Always require approval
    - worker_create: Requires approval when enabled (creates new workers)
    - worker_call: Requires approval when enabled
    """

    def __init__(
        self,
        config: dict,
        id: Optional[str] = None,
        max_retries: int = 1,
    ):
        """Initialize delegation toolset.

        Args:
            config: Toolset configuration dict mapping tool names to config.
                - worker_name: {} to expose _worker_{worker_name}
                - worker_call: {} to expose worker_call
                - worker_create: {} to expose worker_create
            id: Optional toolset ID for durable execution.
            max_retries: Maximum retries for tool calls.
        """
        if config is None:
            config = {}
        if not isinstance(config, dict):
            raise ValueError("Delegation toolset config must be a dict")
        self._config = config
        self._id = id
        self._max_retries = max_retries
        # Cache of worker name -> description (populated in get_tools)
        self._worker_descriptions: Dict[str, str] = {}

    @property
    def id(self) -> str | None:
        """Return toolset ID for durable execution."""
        return self._id

    @property
    def config(self) -> dict:
        """Return the toolset configuration."""
        return self._config

    def _get_configured_workers(self) -> List[str]:
        """Get list of worker names configured as tools."""
        return [name for name in self._config.keys() if name not in _RESERVED_TOOLS]

    def _tool_enabled(self, name: str) -> bool:
        """Return True if a tool is enabled in config."""
        if name not in self._config:
            return False
        value = self._config.get(name)
        if isinstance(value, dict):
            return value.get("enabled", True)
        if isinstance(value, bool):
            return value
        return True

    def _is_worker_tool(self, name: str) -> bool:
        """Check if tool name is a worker tool (worker invocation)."""
        return name.startswith(_WORKER_TOOL_PREFIX)

    def _worker_name_from_tool(self, tool_name: str) -> str:
        """Extract worker name from worker tool name."""
        return tool_name[len(_WORKER_TOOL_PREFIX):]

    def _tool_name_from_worker(self, worker_name: str) -> str:
        """Generate tool name from worker name."""
        return f"{_WORKER_TOOL_PREFIX}{worker_name}"

    def needs_approval(self, name: str, tool_args: dict, ctx: Any) -> ApprovalResult:
        """Determine if tool needs approval.

        Args:
            name: Tool name (worker tool, "worker_create", or "worker_call")
            tool_args: Tool arguments
            ctx: RunContext with deps

        Returns:
            ApprovalResult with status: blocked, pre_approved, or needs_approval
        """
        if self._is_worker_tool(name):
            # Worker tool (worker invocation) - always requires approval
            worker_name = self._worker_name_from_tool(name)
            if worker_name not in self._config:
                return ApprovalResult.blocked(f"Worker tool '{worker_name}' is not configured")
            return ApprovalResult.needs_approval()

        elif name == "worker_create":
            if not self._tool_enabled("worker_create"):
                return ApprovalResult.blocked("worker_create tool is not configured")
            # Worker creation always requires approval
            return ApprovalResult.needs_approval()

        elif name == "worker_call":
            if not self._tool_enabled("worker_call"):
                return ApprovalResult.blocked("worker_call tool is not configured")
            return ApprovalResult.needs_approval()

        # Unknown tool - require approval
        return ApprovalResult.needs_approval()

    def get_approval_description(self, name: str, tool_args: dict, ctx: Any) -> str:
        """Return human-readable description for approval prompt.

        Args:
            name: Tool name (worker tool, "worker_create", or "worker_call")
            tool_args: Tool arguments
            ctx: RunContext with deps

        Returns:
            Description string to show user
        """
        if self._is_worker_tool(name):
            worker_name = self._worker_name_from_tool(name)
            input_data = tool_args.get("input")
            if input_data:
                # Truncate input data for display
                input_str = str(input_data)
                if len(input_str) > 50:
                    input_str = input_str[:50] + "..."
                return f"Call worker '{worker_name}' with: {input_str}"
            return f"Call worker: {worker_name}"

        elif name == "worker_create":
            worker_name = tool_args.get("name", "?")
            return f"Create new worker: {worker_name}"

        elif name == "worker_call":
            target_worker = tool_args.get("worker", "?")
            input_data = tool_args.get("input_data")
            if input_data:
                input_str = str(input_data)
                if len(input_str) > 50:
                    input_str = input_str[:50] + "..."
                return f"Call worker '{target_worker}' with: {input_str}"
            return f"Call worker: {target_worker}"

        return f"{name}({tool_args})"

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool]:
        """Return tools: one per configured worker plus optional helpers.

        For each configured worker, generates a tool with:
        - Name: worker name (prefixed internally for routing)
        - Schema: { input: str }
        - Description: from worker definition or default
        """
        tools: dict[str, ToolsetTool] = {}
        worker_ctx: WorkerContext = ctx.deps

        worker_names = self._get_configured_workers()

        # Generate a tool for each configured worker
        for worker_name in worker_names:
            if not self._tool_enabled(worker_name):
                continue

            description = f"Delegate task to the '{worker_name}' worker"
            definition = None
            if worker_ctx.registry:
                try:
                    definition = worker_ctx.registry.load_definition(worker_name)
                    if definition.description:
                        description = definition.description
                except (FileNotFoundError, ValueError) as e:
                    logger.debug(f"Worker '{worker_name}' not available: {e}")
                    continue
            else:
                logger.debug("No registry available; skipping worker tool '%s'", worker_name)
                continue

            # Cache description for approval messages
            self._worker_descriptions[worker_name] = description

            # Schema for worker tools: input string + optional attachments
            worker_schema = {
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "Input/task description for the worker",
                    },
                },
                "required": ["input"],
            }

            # Add attachments if worker accepts them
            if definition and definition.attachment_policy.max_attachments > 0:
                # Build description based on policy constraints
                attach_desc = "File paths to attach"
                if definition.attachment_policy.allowed_suffixes:
                    suffixes = ", ".join(definition.attachment_policy.allowed_suffixes)
                    attach_desc += f" (allowed: {suffixes})"
                if definition.attachment_policy.max_attachments < 10:
                    attach_desc += f" (max {definition.attachment_policy.max_attachments})"

                worker_schema["properties"]["attachments"] = {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": attach_desc,
                }

            tool_name = self._tool_name_from_worker(worker_name)
            tools[tool_name] = ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name=tool_name,
                    description=description,
                    parameters_json_schema=worker_schema,
                ),
                max_retries=self._max_retries,
                args_validator=TypeAdapter(dict[str, Any]).validator,
            )

        # Include worker_create tool when configured
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

        if self._tool_enabled("worker_create"):
            tools["worker_create"] = ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name="worker_create",
                    description="Persist a new worker definition using the active profile",
                    parameters_json_schema=worker_create_schema,
                ),
                max_retries=self._max_retries,
                args_validator=TypeAdapter(dict[str, Any]).validator,
            )

        # Generic worker_call tool (opt-in via config)
        worker_call_schema = {
            "type": "object",
            "properties": {
                "worker": {
                    "type": "string",
                    "description": "Name of the worker to call",
                },
                "input_data": {
                    "description": "Input data to pass to the worker (optional)",
                },
                "attachments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of file paths to attach",
                },
            },
            "required": ["worker"],
        }

        if self._tool_enabled("worker_call"):
            tools["worker_call"] = ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name="worker_call",
                    description="Call a worker by name",
                    parameters_json_schema=worker_call_schema,
                ),
                max_retries=self._max_retries,
                args_validator=TypeAdapter(dict[str, Any]).validator,
            )

        return tools

    def _prepare_attachments(
        self,
        ctx: WorkerContext,
        worker: str,
        attachments: Optional[List[str]],
    ) -> Optional[List[AttachmentPayload]]:
        """Convert attachment paths to AttachmentPayload objects.

        Returns attachment payloads ready for call_worker_async.
        """
        if not attachments:
            return None

        from pathlib import Path

        attachment_payloads = []
        for attachment_path in attachments:
            path = Path(attachment_path).expanduser().resolve()
            if not path.exists():
                raise FileNotFoundError(f"Attachment not found: {attachment_path}")
            if not path.is_file():
                raise IsADirectoryError(f"Attachment must be a file: {attachment_path}")
            attachment_payloads.append(
                AttachmentPayload(path=path, display_name=attachment_path)
            )

        return attachment_payloads

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[Any],
    ) -> Any:
        """Execute a tool.

        Args:
            name: Tool name (worker tool, "worker_create", or "worker_call")
            tool_args: Tool arguments
            ctx: Run context with WorkerContext as deps
            tool: Tool definition

        Returns:
            Result from the delegated worker or creation status
        """
        # Import here to avoid circular dependency
        from .runtime import call_worker_async, create_worker

        worker_ctx: WorkerContext = ctx.deps

        if self._is_worker_tool(name):
            # Worker tool - delegate to worker
            worker_name = self._worker_name_from_tool(name)
            if not self._tool_enabled(worker_name):
                raise PermissionError(f"Worker tool '{worker_name}' is not configured")
            input_data = tool_args.get("input")
            attachments = tool_args.get("attachments")

            # Prepare attachments if provided
            attachment_payloads = self._prepare_attachments(worker_ctx, worker_name, attachments)

            result = await call_worker_async(
                registry=worker_ctx.registry,
                worker=worker_name,
                input_data=input_data,
                caller_context=worker_ctx,
                attachments=attachment_payloads,
            )
            return result.output

        elif name == "worker_create":
            if not self._tool_enabled("worker_create"):
                raise PermissionError("worker_create tool is not configured")
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

        elif name == "worker_call":
            # Generic worker_call for dynamic routing by name
            if not self._tool_enabled("worker_call"):
                raise PermissionError("worker_call tool is not configured")
            worker_name = tool_args["worker"]
            input_data = tool_args.get("input_data")
            attachments = tool_args.get("attachments")

            attachment_payloads = self._prepare_attachments(worker_ctx, worker_name, attachments)

            result = await call_worker_async(
                registry=worker_ctx.registry,
                worker=worker_name,
                input_data=input_data,
                caller_context=worker_ctx,
                attachments=attachment_payloads,
            )
            return result.output

        else:
            raise ValueError(f"Unknown tool: {name}")


# Backward compatibility alias
AgentToolset = DelegationToolset
