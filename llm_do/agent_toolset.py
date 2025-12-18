"""Agent toolset - workers exposed as direct tools to LLMs.

This module provides AgentToolset which:
1. Exposes each allowed worker as a direct tool (e.g., `summarizer(input=...)`)
2. Keeps worker_create as a separate tool for dynamic worker creation
3. Implements approval logic via `needs_approval()` returning ApprovalResult
4. Provides custom descriptions via `get_approval_description()`

This replaces the old worker_call indirection with direct tool invocation:
- Before: `worker_call(worker="summarizer", input_data="...")`
- After: `summarizer(input="...")`
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

# Prefix for agent tools to identify them in call_tool
_AGENT_TOOL_PREFIX = "_agent_"


class AgentToolset(AbstractToolset[WorkerContext]):
    """Agent toolset - workers exposed as direct tools.

    Each allowed worker is exposed as a tool with the worker's name.
    The `needs_approval()` method is called by ApprovalToolset wrapper
    to determine if a delegation needs user approval.

    Approval logic:
    - Agent tools (worker names): Always require approval
    - worker_create: Always requires approval (creates new workers)
    """

    def __init__(
        self,
        config: dict,
        id: Optional[str] = None,
        max_retries: int = 1,
    ):
        """Initialize agent toolset.

        Args:
            config: Toolset configuration dict with:
                - allow_workers: List of worker names or ['*'] for all
            id: Optional toolset ID for durable execution.
            max_retries: Maximum retries for tool calls.
        """
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

    def _get_allowed_workers(self) -> List[str]:
        """Get list of allowed worker names from config."""
        return self._config.get("allow_workers", [])

    def _is_agent_tool(self, name: str) -> bool:
        """Check if tool name is an agent tool (worker invocation)."""
        return name.startswith(_AGENT_TOOL_PREFIX)

    def _worker_name_from_tool(self, tool_name: str) -> str:
        """Extract worker name from agent tool name."""
        return tool_name[len(_AGENT_TOOL_PREFIX):]

    def _tool_name_from_worker(self, worker_name: str) -> str:
        """Generate tool name from worker name."""
        return f"{_AGENT_TOOL_PREFIX}{worker_name}"

    def needs_approval(self, name: str, tool_args: dict, ctx: Any) -> ApprovalResult:
        """Determine if tool needs approval.

        Args:
            name: Tool name (worker name, "worker_create", or "worker_call")
            tool_args: Tool arguments
            ctx: RunContext with deps

        Returns:
            ApprovalResult with status: blocked, pre_approved, or needs_approval
        """
        if self._is_agent_tool(name):
            # Agent tool (worker invocation) - always requires approval
            return ApprovalResult.needs_approval()

        elif name == "worker_create":
            # Worker creation always requires approval
            return ApprovalResult.needs_approval()

        elif name == "worker_call":
            # Generic worker call - always requires approval
            return ApprovalResult.needs_approval()

        # Unknown tool - require approval
        return ApprovalResult.needs_approval()

    def get_approval_description(self, name: str, tool_args: dict, ctx: Any) -> str:
        """Return human-readable description for approval prompt.

        Args:
            name: Tool name (worker name, "worker_create", or "worker_call")
            tool_args: Tool arguments
            ctx: RunContext with deps

        Returns:
            Description string to show user
        """
        if self._is_agent_tool(name):
            worker_name = self._worker_name_from_tool(name)
            input_data = tool_args.get("input")
            if input_data:
                # Truncate input data for display
                input_str = str(input_data)
                if len(input_str) > 50:
                    input_str = input_str[:50] + "..."
                return f"Call agent '{worker_name}' with: {input_str}"
            return f"Call agent: {worker_name}"

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
        """Return tools: one per allowed worker + worker_create.

        For each allowed worker, generates a tool with:
        - Name: worker name (prefixed internally for routing)
        - Schema: { input: str }
        - Description: from worker definition or default
        """
        tools: dict[str, ToolsetTool] = {}
        worker_ctx: WorkerContext = ctx.deps

        # Get allowed workers
        allow_workers = self._get_allowed_workers()

        if allow_workers:
            # Resolve actual worker names if '*' is used
            if '*' in allow_workers:
                # Get all available workers from registry
                if worker_ctx.registry:
                    worker_names = list(worker_ctx.registry.list_workers())
                else:
                    worker_names = []
            else:
                worker_names = allow_workers

            # Generate a tool for each allowed worker
            for worker_name in worker_names:
                # Get worker description from registry
                description = f"Delegate task to the '{worker_name}' agent"
                if worker_ctx.registry:
                    try:
                        definition = worker_ctx.registry.load_definition(worker_name)
                        if definition.description:
                            description = definition.description
                    except Exception:
                        # Worker not found - skip it
                        logger.debug(f"Worker '{worker_name}' not found, skipping tool generation")
                        continue

                # Cache description for approval messages
                self._worker_descriptions[worker_name] = description

                # Schema for agent tools: just an input string
                agent_schema = {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": "Input/task description for the agent",
                        },
                    },
                    "required": ["input"],
                }

                tool_name = self._tool_name_from_worker(worker_name)
                tools[tool_name] = ToolsetTool(
                    toolset=self,
                    tool_def=ToolDefinition(
                        name=tool_name,
                        description=description,
                        parameters_json_schema=agent_schema,
                    ),
                    max_retries=self._max_retries,
                    args_validator=TypeAdapter(dict[str, Any]).validator,
                )

        # Always include worker_create tool
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

        # Generic worker_call for dynamically created workers (backward compatibility)
        # This allows calling workers created via worker_create during the same run
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

        tools["worker_call"] = ToolsetTool(
            toolset=self,
            tool_def=ToolDefinition(
                name="worker_call",
                description="Call a worker by name (use for dynamically created workers)",
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
            name: Tool name (worker name or "worker_create")
            tool_args: Tool arguments
            ctx: Run context with WorkerContext as deps
            tool: Tool definition

        Returns:
            Result from the delegated worker or creation status
        """
        # Import here to avoid circular dependency
        from .runtime import call_worker_async, create_worker

        worker_ctx: WorkerContext = ctx.deps

        if self._is_agent_tool(name):
            # Agent tool - delegate to worker
            worker_name = self._worker_name_from_tool(name)
            input_data = tool_args.get("input")

            result = await call_worker_async(
                registry=worker_ctx.registry,
                worker=worker_name,
                input_data=input_data,
                caller_context=worker_ctx,
            )
            return result.output

        elif name == "worker_create":
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
            # Generic worker_call for dynamically created workers
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
DelegationToolset = AgentToolset
