"""Custom tools as a PydanticAI toolset with approval.

This module provides CustomToolset which:
1. Loads custom tools from a tools.py module
2. Exposes them as PydanticAI tools
3. Enforces approval for all custom tools (secure by default)
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
    """Custom tools toolset with per-tool approval configuration.

    This toolset loads and exposes custom tools from a Python module.
    The `needs_approval()` method is called by ApprovalToolset wrapper
    to determine if a tool call needs user approval.

    Tools default to requiring approval (secure by default).
    """

    def __init__(
        self,
        config: dict,
        worker_name: str,
        tools_path: Path,
        id: Optional[str] = None,
        max_retries: int = 1,
    ):
        """Initialize custom toolset.

        Args:
            config: Custom tools configuration dict (tool_name -> {approval_required, allowed})
            worker_name: Name of the worker (for module naming)
            tools_path: Path to the tools.py file
            id: Optional toolset ID for durable execution.
            max_retries: Maximum retries for tool calls.
        """
        self._config = config
        self._worker_name = worker_name
        self._tools_path = tools_path
        self._id = id
        self._max_retries = max_retries
        self._module = None
        self._functions: dict[str, Callable] = {}

        # Filter to only allowed tools
        self._allowed_tools = [
            name for name, tool_config in config.items()
            if tool_config.get("allowed", True)
        ]

    @property
    def id(self) -> str | None:
        """Return toolset ID for durable execution."""
        return self._id

    @property
    def config(self) -> dict:
        """Return the toolset configuration."""
        return self._config

    def needs_approval(self, name: str, tool_args: dict) -> bool | dict:
        """Check per-tool approval configuration.

        Args:
            name: Tool name
            tool_args: Tool arguments

        Returns:
            - False: No approval needed (approval_required=false in config)
            - dict with description for approval prompt

        Raises:
            PermissionError: If tool is not allowed
        """
        # Get tool config (default to secure: approval required, allowed)
        tool_config = self._config.get(name, {})

        # Check if tool is allowed (default: True)
        if not tool_config.get("allowed", True):
            raise PermissionError(f"Custom tool '{name}' is not allowed")

        # Check if approval is required (default: True - secure by default)
        if not tool_config.get("approval_required", True):
            return False  # Pre-approved

        # Format args for display
        args_preview = ", ".join(f"{k}={v!r}" for k, v in list(tool_args.items())[:3])
        if len(tool_args) > 3:
            args_preview += ", ..."

        return {"description": f"Custom tool: {name}({args_preview})"}

    def _load_module(self) -> None:
        """Load the tools module and discover functions."""
        if self._module is not None:
            return

        if not self._tools_path.exists():
            logger.warning(f"Custom tools path does not exist: {self._tools_path}")
            return

        # Load the module from the file path
        spec = importlib.util.spec_from_file_location(
            f"{self._worker_name}_tools", self._tools_path
        )
        if spec is None or spec.loader is None:
            logger.warning(f"Could not load custom tools from {self._tools_path}")
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"Error loading custom tools from {self._tools_path}: {e}")
            return

        self._module = module

        # Discover allowed functions
        for tool_name in self._allowed_tools:
            if not hasattr(module, tool_name):
                logger.warning(f"Custom tool '{tool_name}' not found in {self._tools_path}")
                continue

            obj = getattr(module, tool_name)
            if not (
                callable(obj)
                and inspect.isfunction(obj)
                and obj.__module__ == module.__name__
            ):
                logger.warning(f"Custom tool '{tool_name}' is not a function in {self._tools_path}")
                continue

            self._functions[tool_name] = obj
            logger.debug(f"Discovered custom tool: {tool_name}")

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool]:
        """Return tool definitions for all discovered custom tools."""
        self._load_module()

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
