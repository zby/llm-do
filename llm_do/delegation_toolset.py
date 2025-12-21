"""Delegation toolset - workers exposed as direct tools to LLMs.

This module provides DelegationToolset which:
1. Exposes configured workers as direct tools (e.g., `summarizer(input=...)`)
2. Optionally exposes worker_create and worker_call tools when configured
3. Implements approval logic via `needs_approval()` returning ApprovalResult
4. Provides custom descriptions via `get_approval_description()`

Worker tools use the same name as the worker (no prefix):
- Configured worker `summarizer` -> tool `summarizer`
- worker_call is restricted to session-generated workers only

Tool schema is dynamic:
- All worker tools have `input: str` (required)
- If worker accepts attachments (attachment_policy.max_attachments > 0),
  adds optional `attachments: list[str]` parameter
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from pydantic import TypeAdapter
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.tools import ToolDefinition
from pydantic_ai_blocking_approval import ApprovalResult

from .attachments import AttachmentPayload
from .types import WorkerContext, WorkerSpec

logger = logging.getLogger(__name__)

# Reserved tool names that cannot be used as worker names
_RESERVED_TOOLS = {"worker_call", "worker_create"}
_SHELL_TOOLSET_KEYS = {"shell", "llm_do.shell.toolset.ShellToolset"}
_FILESYSTEM_TOOLSET_KEYS = {"filesystem", "llm_do.filesystem_toolset.FileSystemToolset"}
_CUSTOM_TOOLSET_KEYS = {"custom", "llm_do.custom_toolset.CustomToolset"}
_FILESYSTEM_TOOL_NAMES = {"read_file", "write_file", "list_files"}
_SHELL_TOOL_NAMES = {"shell"}
_CUSTOM_TOOLSET_APPROVAL_KEY = "_approval_config"
# Server-side tools executed by LLM providers (tool_type values from ServerSideToolConfig)
_SERVER_SIDE_TOOL_NAMES = {"web_search", "web_fetch", "code_execution", "image_generation"}


class DelegationToolset(AbstractToolset[WorkerContext]):
    """Delegation toolset - workers exposed as direct tools.

    Each configured worker is exposed as a tool with the worker's name.
    The `needs_approval()` method is called by ApprovalToolset wrapper
    to determine if a delegation needs user approval.

    Approval logic:
    - Worker tools (worker names): Always require approval
    - worker_create: Requires approval when enabled (creates new workers)
    - worker_call: Requires approval for session-generated workers only, blocked otherwise
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
                - worker_name: {} to expose worker as a direct tool
                - worker_call: {} to expose worker_call (session-generated only)
                - worker_create: {} to expose worker_create
            id: Optional toolset ID for durable execution.
            max_retries: Maximum retries for tool calls.

        Raises:
            ValueError: If a worker name conflicts with a reserved tool name.
        """
        if config is None:
            config = {}
        if not isinstance(config, dict):
            raise ValueError("Delegation toolset config must be a dict")
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

    def _get_configured_workers(self) -> List[str]:
        """Get list of worker names configured as tools."""
        return [name for name in self._config.keys() if name not in _RESERVED_TOOLS]

    def _get_toolset_config(
        self,
        toolsets: dict[str, Any],
        keys: set[str],
    ) -> Optional[Any]:
        """Return the toolset config for a known alias/class path if present."""
        for key in keys:
            if key in toolsets:
                return toolsets[key]
        return None

    def _collect_reserved_tool_names(self, worker_ctx: WorkerContext) -> set[str]:
        """Collect tool names that would collide with worker tools."""
        reserved = set(_RESERVED_TOOLS)
        toolsets = worker_ctx.worker.toolsets or {}

        if any(key in toolsets for key in _SHELL_TOOLSET_KEYS):
            reserved.update(_SHELL_TOOL_NAMES)

        if any(key in toolsets for key in _FILESYSTEM_TOOLSET_KEYS):
            reserved.update(_FILESYSTEM_TOOL_NAMES)

        custom_config = self._get_toolset_config(toolsets, _CUSTOM_TOOLSET_KEYS)
        if isinstance(custom_config, dict):
            reserved.update(
                name for name in custom_config.keys() if name != _CUSTOM_TOOLSET_APPROVAL_KEY
            )

        # Check server-side tools (provider-executed tools like web_search)
        server_side_tools = worker_ctx.worker.server_side_tools or []
        for tool_config in server_side_tools:
            if tool_config.tool_type in _SERVER_SIDE_TOOL_NAMES:
                reserved.add(tool_config.tool_type)

        return reserved

    def _validate_worker_tool_names(self, worker_ctx: WorkerContext) -> None:
        """Fail fast on worker tool name collisions or reserved names."""
        reserved = self._collect_reserved_tool_names(worker_ctx)
        worker_names = self._get_configured_workers()
        collisions = sorted(set(worker_names) & reserved)
        if collisions:
            names = ", ".join(collisions)
            raise ValueError(
                "Worker names conflict with other tool names: "
                f"{names}. Rename the worker(s) or disable the conflicting toolset(s)."
            )

        registry = getattr(worker_ctx, "registry", None)
        if registry is None:
            return
        for reserved_name in _RESERVED_TOOLS:
            if reserved_name in self._config and registry.worker_exists(reserved_name):
                raise ValueError(
                    f"Worker name '{reserved_name}' is reserved for delegation tools. "
                    "Rename the worker to expose it as a tool."
                )

    def _is_configured_worker(self, worker_name: str) -> bool:
        """Return True if the worker is configured and enabled."""
        if worker_name in _RESERVED_TOOLS:
            return False
        if worker_name not in self._config:
            return False
        return self._tool_enabled(worker_name)

    def _is_generated_worker(self, worker_ctx: WorkerContext, worker_name: str) -> bool:
        """Return True if the worker was generated in this session."""
        registry = getattr(worker_ctx, "registry", None)
        if registry is None:
            return False
        is_generated = getattr(registry, "is_generated", None)
        if is_generated is None:
            return False
        return bool(is_generated(worker_name))

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

    def _get_tool_config(self, name: str, key: str, default: Any = None) -> Any:
        """Get a config value for a tool.

        Args:
            name: Tool name (e.g., "worker_create")
            key: Config key to retrieve (e.g., "output_dir")
            default: Default value if not found

        Returns:
            The config value or default
        """
        value = self._config.get(name)
        if isinstance(value, dict):
            return value.get(key, default)
        return default

    def needs_approval(self, name: str, tool_args: dict, ctx: Any) -> ApprovalResult:
        """Determine if tool needs approval.

        Args:
            name: Tool name (worker name, "worker_create", or "worker_call")
            tool_args: Tool arguments
            ctx: RunContext with deps

        Returns:
            ApprovalResult with status: blocked, pre_approved, or needs_approval
        """
        if name == "worker_create":
            if not self._tool_enabled("worker_create"):
                return ApprovalResult.blocked("worker_create tool is not configured")
            # Worker creation always requires approval
            return ApprovalResult.needs_approval()

        elif name == "worker_call":
            if not self._tool_enabled("worker_call"):
                return ApprovalResult.blocked("worker_call tool is not configured")
            worker_name = tool_args.get("worker")
            worker_ctx = getattr(ctx, "deps", None)

            # worker_call is restricted to session-generated workers only
            if worker_name and worker_ctx:
                if self._is_generated_worker(worker_ctx, worker_name):
                    return ApprovalResult.needs_approval()

            # Block if not a session-generated worker
            return ApprovalResult.blocked(
                f"worker_call only supports session-generated workers. "
                f"Use the '{worker_name}' tool directly for configured workers."
            )

        elif self._is_configured_worker(name):
            # Configured worker tool - always requires approval
            return ApprovalResult.needs_approval()

        # Unknown tool - block it
        return ApprovalResult.blocked(f"Unknown tool: {name}")

    def get_approval_description(self, name: str, tool_args: dict, ctx: Any) -> str:
        """Return human-readable description for approval prompt.

        Args:
            name: Tool name (worker name, "worker_create", or "worker_call")
            tool_args: Tool arguments
            ctx: RunContext with deps

        Returns:
            Description string to show user
        """
        def summarize_input(input_data: Any) -> Optional[str]:
            if input_data is None:
                return None
            input_str = str(input_data)
            if len(input_str) > 50:
                input_str = input_str[:50] + "..."
            return input_str

        def summarize_attachments(attachments: Optional[List[str]]) -> Optional[str]:
            if not attachments:
                return None
            shown = attachments[:3]
            summary = ", ".join(shown)
            if len(attachments) > 3:
                summary += f", +{len(attachments) - 3} more"
            return summary

        def build_details(input_data: Any, attachments: Optional[List[str]]) -> Optional[str]:
            details = []
            input_str = summarize_input(input_data)
            if input_str is not None:
                details.append(f"input: {input_str}")
            attach_str = summarize_attachments(attachments)
            if attach_str is not None:
                details.append(f"attachments: {attach_str}")
            return ", ".join(details) if details else None

        if name == "worker_create":
            worker_name = tool_args.get("name", "?")
            return f"Create new worker: {worker_name}"

        elif name == "worker_call":
            target_worker = tool_args.get("worker", "?")
            details = build_details(tool_args.get("input_data"), tool_args.get("attachments"))
            if details:
                return f"Call worker '{target_worker}' with {details}"
            return f"Call worker: {target_worker}"

        elif self._is_configured_worker(name):
            # Worker tool - name is the worker name directly
            details = build_details(tool_args.get("input"), tool_args.get("attachments"))
            if details:
                return f"Call worker '{name}' with {details}"
            return f"Call worker: {name}"

        return f"{name}({tool_args})"

    async def _invoke_worker(
        self,
        worker_ctx: WorkerContext,
        worker_name: str,
        input_data: Any,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        """Internal helper to invoke a worker.

        This is the common execution path for both configured worker tools
        and worker_call. It handles attachment preparation and calls the
        runtime's call_worker_async.

        Args:
            worker_ctx: WorkerContext with registry and other context
            worker_name: Name of the worker to invoke
            input_data: Input data to pass to the worker
            attachments: Optional list of file paths to attach

        Returns:
            The worker's output result
        """
        from .runtime import call_worker_async

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

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool]:
        """Return tools: one per configured worker plus optional helpers.

        For each configured worker, generates a tool with:
        - Name: worker name (same as worker, no prefix)
        - Schema: { input: str }
        - Description: from worker definition or default
        """
        tools: dict[str, ToolsetTool] = {}
        worker_ctx: WorkerContext = ctx.deps

        self._validate_worker_tool_names(worker_ctx)

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
                    logger.warning(f"Configured worker '{worker_name}' not available: {e}")
                    continue
            else:
                logger.warning("No registry available; skipping worker tool '%s'", worker_name)
                continue

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

            # Tool name is the worker name directly (no prefix)
            tools[worker_name] = ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name=worker_name,
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
        # Restricted to session-generated workers only
        worker_call_schema = {
            "type": "object",
            "properties": {
                "worker": {
                    "type": "string",
                    "description": "Name of a session-generated worker to call",
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
                    description="Call a session-generated worker by name",
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
            name: Tool name (worker name, "worker_create", or "worker_call")
            tool_args: Tool arguments
            ctx: Run context with WorkerContext as deps
            tool: Tool definition

        Returns:
            Result from the delegated worker or creation status
        """
        from .runtime import create_worker

        worker_ctx: WorkerContext = ctx.deps

        if name == "worker_create":
            if not self._tool_enabled("worker_create"):
                raise PermissionError("worker_create tool is not configured")
            spec = WorkerSpec(
                name=tool_args["name"],
                instructions=tool_args["instructions"],
                description=tool_args.get("description"),
                model=tool_args.get("model"),
                output_schema_ref=tool_args.get("output_schema_ref"),
            )
            # Get output_dir from worker_create config (e.g., output_dir: ./workers/generated)
            output_dir = self._get_tool_config("worker_create", "output_dir")
            created = create_worker(
                registry=worker_ctx.registry,
                spec=spec,
                defaults=worker_ctx.creation_defaults,
                force=tool_args.get("force", False),
                output_dir=output_dir,
            )
            return created.model_dump(mode="json")

        elif name == "worker_call":
            # Generic worker_call for session-generated workers only
            if not self._tool_enabled("worker_call"):
                raise PermissionError("worker_call tool is not configured")
            worker_name = tool_args["worker"]

            # Check for workers_dir config - if set, construct path to worker
            workers_dir = self._get_tool_config("worker_call", "workers_dir")
            if workers_dir:
                # Use explicit path: {workers_dir}/{name}/worker.worker
                from pathlib import Path
                worker_path = str(Path(workers_dir) / worker_name / "worker.worker")
                worker_ref = worker_path
            else:
                # Default behavior: check if it's a session-generated worker
                if not self._is_generated_worker(worker_ctx, worker_name):
                    raise PermissionError(
                        f"worker_call only supports session-generated workers. "
                        f"Worker '{worker_name}' is not available."
                    )
                worker_ref = worker_name

            input_data = tool_args.get("input_data")
            attachments = tool_args.get("attachments")
            return await self._invoke_worker(worker_ctx, worker_ref, input_data, attachments)

        elif self._is_configured_worker(name):
            # Configured worker tool - name is the worker name directly
            input_data = tool_args.get("input")
            attachments = tool_args.get("attachments")
            return await self._invoke_worker(worker_ctx, name, input_data, attachments)

        else:
            raise ValueError(f"Unknown tool: {name}")


# Backward compatibility alias
AgentToolset = DelegationToolset
