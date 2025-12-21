"""Custom tools as a PydanticAI toolset.

This module provides CustomToolset which:
1. Loads custom tools from a tools.py module
2. Exposes only tools listed in config (whitelist model)
3. Wraps with ApprovalToolset for approval handling
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Optional, get_type_hints

from pydantic import TypeAdapter, create_model
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.tools import ToolDefinition

from .tool_context import get_context_param, tool_context
from .types import WorkerContext

logger = logging.getLogger(__name__)

def _build_schema_from_function(
    func: Callable,
    *,
    skip_params: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Build JSON schema from a function's signature using Pydantic.

    Uses Pydantic's create_model to dynamically create a model from the
    function signature, then generates the JSON schema. This properly handles:
    - Optional types (Union[X, None])
    - Union types (anyOf)
    - List, Dict, and other generic types
    - Default values
    """
    sig = inspect.signature(func)
    skip_params = skip_params or set()
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    # Build field definitions for create_model
    # Format: {name: (type, default) or (type, FieldInfo)}
    field_definitions: dict[str, Any] = {}

    for name, param in sig.parameters.items():
        if name in skip_params:
            continue
        # Get type annotation (default to Any if not specified)
        annotation = hints.get(name, Any)

        # Get default value
        if param.default is inspect.Parameter.empty:
            # Required field - use ... (Ellipsis) as marker
            field_definitions[name] = (annotation, ...)
        else:
            # Optional field with default
            field_definitions[name] = (annotation, param.default)

    # Create a dynamic Pydantic model
    try:
        DynamicModel = create_model(f"{func.__name__}_params", **field_definitions)
        schema = DynamicModel.model_json_schema()

        # Clean up schema - remove $defs if present (inline definitions)
        # and remove title since we don't need it
        schema.pop("$defs", None)
        schema.pop("title", None)

        return schema
    except Exception as e:
        logger.warning(f"Failed to generate Pydantic schema for {func.__name__}: {e}")
        # Fallback to basic schema
        return {"type": "object", "properties": {}}


class CustomToolset(AbstractToolset[WorkerContext]):
    """Custom tools toolset with whitelist-based tool exposure.

    This toolset loads and exposes custom tools from a Python module.
    Only tools listed in config are exposed to the LLM (whitelist model).

    Approval is handled by wrapping with ApprovalToolset.
    """

    def __init__(
        self,
        config: dict,
        id: Optional[str] = None,
        max_retries: int = 1,
    ):
        """Initialize custom toolset.

        Args:
            config: Custom tools configuration dict (tool_name -> {pre_approved}).
                    Only tools in config are exposed (whitelist model).
            id: Optional toolset ID for durable execution.
            max_retries: Maximum retries for tool calls.
        """
        self._config = config
        self._id = id
        self._max_retries = max_retries
        self._module = None
        self._functions: dict[str, Callable] = {}
        self._context_params: dict[str, str] = {}

    @property
    def id(self) -> str | None:
        """Return toolset ID for durable execution."""
        return self._id

    @property
    def config(self) -> dict:
        """Return the toolset configuration."""
        return self._config

    def _load_module(self, worker_name: str, tools_path: Path) -> None:
        """Load the tools module and discover functions.

        Args:
            worker_name: Name of the worker (for module naming)
            tools_path: Path to the tools.py file
        """
        if self._module is not None:
            return

        if not tools_path.exists():
            logger.warning(f"Custom tools path does not exist: {tools_path}")
            return

        # Load the module from the file path
        # Use path hash to avoid collisions when workers have the same name
        path_hash = hashlib.md5(str(tools_path.resolve()).encode()).hexdigest()[:8]
        module_name = f"{worker_name}_tools_{path_hash}"
        spec = importlib.util.spec_from_file_location(module_name, tools_path)
        if spec is None or spec.loader is None:
            logger.warning(f"Could not load custom tools from {tools_path}")
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"Error loading custom tools from {tools_path}: {e}")
            return

        self._module = module

        # Discover whitelisted functions (only tools in config are exposed)
        for tool_name in self._config.keys():
            if not hasattr(module, tool_name):
                logger.warning(f"Custom tool '{tool_name}' not found in {tools_path}")
                continue

            obj = getattr(module, tool_name)
            if not (
                callable(obj)
                and inspect.isfunction(obj)
                and obj.__module__ == module.__name__
            ):
                logger.warning(f"Custom tool '{tool_name}' is not a function in {tools_path}")
                continue

            context_param = get_context_param(obj)
            if context_param:
                sig = inspect.signature(obj)
                if context_param not in sig.parameters:
                    raise ValueError(
                        f"Custom tool '{tool_name}' is marked with @tool_context "
                        f"but does not accept parameter '{context_param}'."
                    )
                self._context_params[tool_name] = context_param

            self._functions[tool_name] = obj
            logger.debug(f"Discovered custom tool: {tool_name}")

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool]:
        """Return tool definitions for all discovered custom tools.

        Loads the tools module lazily from ctx.deps on first call.
        """
        # Get worker_name and tools_path from context
        worker_context: WorkerContext = ctx.deps
        worker_name = worker_context.worker.name
        tools_path = worker_context.custom_tools_path

        if tools_path is None:
            logger.warning(f"No custom tools path for worker '{worker_name}'")
            return {}

        self._load_module(worker_name, tools_path)

        tools = {}
        for name, func in self._functions.items():
            skip_params = set()
            context_param = self._context_params.get(name)
            if context_param:
                skip_params.add(context_param)
            schema = _build_schema_from_function(func, skip_params=skip_params)

            tools[name] = ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name=name,
                    description=func.__doc__ or f"Custom tool: {name}",
                    parameters_json_schema=schema,
                ),
                max_retries=self._max_retries,
                args_validator=TypeAdapter(dict[str, Any]).validator,
            )

        return tools

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[Any],
    ) -> Any:
        """Execute a custom tool.

        Args:
            name: Tool name
            tool_args: Tool arguments
            ctx: Run context (unused here, approval already handled by wrapper)
            tool: Tool definition

        Returns:
            Result from the custom function
        """
        if name not in self._functions:
            raise ValueError(f"Unknown custom tool: {name}")

        func = self._functions[name]
        context_param = self._context_params.get(name)
        if context_param:
            tool_args = dict(tool_args)
            tool_args[context_param] = ctx.deps

        # Handle both sync and async functions
        if inspect.iscoroutinefunction(func):
            return await func(**tool_args)
        else:
            return func(**tool_args)
