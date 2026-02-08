"""Tool and toolset resolution helpers for project linker modules."""
from __future__ import annotations

import functools
import inspect
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic_ai.tools import Tool
from pydantic_ai.toolsets import AbstractToolset, ToolsetFunc

from ..runtime.tooling import ToolDef, ToolsetDef, is_tool_def, is_toolset_def


def _attach_registry_name(obj: Any, name: str) -> None:
    """Attach registry name metadata when possible (best-effort)."""
    try:
        setattr(obj, "_llm_do_registry_name", name)
    except Exception:
        return


def _wrap_toolset_func_validation(
    toolset_func: ToolsetFunc[Any],
    name: str,
) -> ToolsetFunc[Any]:
    """Wrap a ToolsetFunc to validate its return type and add context to errors."""

    @functools.wraps(toolset_func)
    async def _validated(ctx: Any) -> AbstractToolset[Any] | None:
        toolset = toolset_func(ctx)
        if inspect.isawaitable(toolset):
            toolset = await toolset
        if toolset is None:
            return None
        if not isinstance(toolset, AbstractToolset):
            raise TypeError(
                f"Toolset '{name}' factory returned {type(toolset)!r}; "
                "expected AbstractToolset or None."
            )
        return toolset

    _attach_registry_name(_validated, name)
    return _validated


def resolve_tool_defs(
    tools_definition: Sequence[str],
    *,
    available_tools: Mapping[str, ToolDef],
    agent_name: str = "",
) -> list[ToolDef]:
    """Resolve tool defs declared in an agent file."""
    tools: list[ToolDef] = []
    for tool_name in tools_definition:
        tool = available_tools.get(tool_name)
        if tool is None:
            available = sorted(available_tools.keys())
            raise ValueError(
                f"Unknown tool {tool_name!r} for agent {agent_name!r}. "
                f"Available: {available}"
            )
        if not is_tool_def(tool) or isinstance(tool, AbstractToolset):
            raise TypeError(
                f"Tool registry entry {tool_name!r} is not a tool definition: {tool!r}"
            )
        _attach_registry_name(tool, tool_name)
        tools.append(tool)
    return tools


def resolve_toolset_defs(
    toolsets_definition: Sequence[str],
    *,
    available_toolsets: Mapping[str, ToolsetDef],
    agent_name: str = "",
) -> list[ToolsetDef]:
    """Resolve toolset defs declared in an agent file."""
    toolsets: list[ToolsetDef] = []
    for toolset_name in toolsets_definition:
        toolset = available_toolsets.get(toolset_name)
        if toolset is None:
            available = sorted(available_toolsets.keys())
            raise ValueError(
                f"Unknown toolset {toolset_name!r} for agent {agent_name!r}. "
                f"Available: {available}"
            )
        if not is_toolset_def(toolset) or isinstance(toolset, Tool):
            raise TypeError(
                f"Toolset registry entry {toolset_name!r} is not a toolset definition: {toolset!r}"
            )
        if isinstance(toolset, AbstractToolset):
            _attach_registry_name(toolset, toolset_name)
            toolsets.append(toolset)
            continue
        wrapped = _wrap_toolset_func_validation(toolset, toolset_name)
        toolsets.append(wrapped)
    return toolsets
