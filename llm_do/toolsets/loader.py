"""Compatibility re-exports for tool/toolset helpers."""

from ..project.tool_resolution import resolve_tool_defs, resolve_toolset_defs
from ..runtime.tooling import (
    ToolDef,
    ToolsetDef,
    is_tool_def,
    is_toolset_def,
    tool_def_name,
)

__all__ = [
    "ToolDef",
    "ToolsetDef",
    "tool_def_name",
    "is_tool_def",
    "is_toolset_def",
    "resolve_tool_defs",
    "resolve_toolset_defs",
]
