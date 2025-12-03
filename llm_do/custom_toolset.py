"""Custom tools as a PydanticAI toolset.

This module provides CustomToolset which:
1. Loads custom tools from a tools.py module
2. Exposes only tools listed in config (whitelist model)
3. Wraps with ApprovalToolset for approval handling
"""
from __future__ import annotations

import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional, get_type_hints

from pydantic import TypeAdapter
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.tools import ToolDefinition

from .types import WorkerContext

logger = logging.getLogger(__name__)


def _python_type_to_json_schema(python_type: Any) -> dict[str, Any]:
    """Convert a Python type annotation to JSON schema."""
    if python_type is None or python_type is type(None):
        return {"type": "null"}
    elif python_type is str:
        return {"type": "string"}
    elif python_type is int:
        return {"type": "integer"}
    elif python_type is float:
        return {"type": "number"}
    elif python_type is bool:
        return {"type": "boolean"}
    elif hasattr(python_type, "__origin__"):
        # Handle generic types like List[str], Optional[int], etc.
        origin = python_type.__origin__
        if origin is list:
            args = getattr(python_type, "__args__", (Any,))
            return {
                "type": "array",
                "items": _python_type_to_json_schema(args[0]) if args else {},
            }
        elif origin is dict:
            return {"type": "object"}
        # Optional[X] is Union[X, None]
        elif hasattr(origin, "__mro__") and type(None) in getattr(python_type, "__args__", ()):
            args = [a for a in python_type.__args__ if a is not type(None)]
            if len(args) == 1:
                return _python_type_to_json_schema(args[0])
    # Default fallback
    return {}


def _build_schema_from_function(func: Callable) -> dict[str, Any]:
    """Build JSON schema from a function's signature."""
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    properties = {}
    required = []

    for name, param in sig.parameters.items():
        prop = {}

        # Get type from hints
        if name in hints:
            prop = _python_type_to_json_schema(hints[name])

        # Get description from docstring if available
        # (Simple extraction - could be enhanced with docstring parsing)

        properties[name] = prop if prop else {}

        # Required if no default
        if param.default is inspect.Parameter.empty:
            required.append(name)

    schema = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


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
        spec = importlib.util.spec_from_file_location(
            f"{worker_name}_tools", tools_path
        )
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
            schema = _build_schema_from_function(func)

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

        # Handle both sync and async functions
        if inspect.iscoroutinefunction(func):
            return await func(**tool_args)
        else:
            return func(**tool_args)
