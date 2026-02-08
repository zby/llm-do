"""Runtime-owned tool and toolset type surface."""
from __future__ import annotations

from typing import Any, TypeAlias

from pydantic_ai.tools import Tool, ToolFuncEither
from pydantic_ai.toolsets import AbstractToolset, ToolsetFunc

ToolDef: TypeAlias = Tool[Any] | ToolFuncEither[Any, ...]
ToolsetDef: TypeAlias = AbstractToolset[Any] | ToolsetFunc[Any]


def tool_def_name(tool: ToolDef) -> str:
    """Return the callable name for a tool definition."""
    if isinstance(tool, Tool):
        return tool.name
    return getattr(tool, "__name__", type(tool).__name__)


def is_tool_def(value: Any) -> bool:
    return isinstance(value, Tool) or callable(value)


def is_toolset_def(value: Any) -> bool:
    return isinstance(value, AbstractToolset) or callable(value)
