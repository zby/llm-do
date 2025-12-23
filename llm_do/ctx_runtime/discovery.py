"""Module loading and AbstractToolset discovery.

This module provides functions to:
- Load Python modules from file paths
- Discover AbstractToolset instances (including FunctionToolset)
- Discover ToolEntry/WorkerEntry instances

Discovery uses isinstance() checks to find toolset instances
in module attributes.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from pydantic_ai.toolsets import AbstractToolset

from .entries import ToolEntry, WorkerEntry, ToolsetToolEntry


def load_module(path: str | Path) -> ModuleType:
    """Load a Python module from a file path.

    Args:
        path: Path to Python file

    Returns:
        Loaded module

    Raises:
        ImportError: If module cannot be loaded
    """
    path = Path(path).resolve()
    # Use full path as module name to avoid collisions between files with same stem
    # e.g., /foo/tools.py and /bar/tools.py become unique module names
    module_name = f"_llm_do_runtime_{path.stem}_{hash(str(path)) & 0xFFFFFFFF:08x}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def discover_toolsets_from_module(module: ModuleType) -> dict[str, AbstractToolset[Any]]:
    """Discover AbstractToolset instances from a module.

    Scans module attributes for instances of AbstractToolset
    (including FunctionToolset) and returns them by attribute name.

    Args:
        module: Loaded Python module

    Returns:
        Dict mapping attribute names to toolset instances
    """
    toolsets: dict[str, AbstractToolset[Any]] = {}
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, AbstractToolset):
            toolsets[name] = obj
    return toolsets


def discover_entries_from_module(module: ModuleType) -> list[ToolEntry | WorkerEntry]:
    """Discover ToolEntry and WorkerEntry instances from a module.

    Args:
        module: Loaded Python module

    Returns:
        List of discovered entries
    """
    entries: list[ToolEntry | WorkerEntry] = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, (ToolEntry, WorkerEntry)):
            entries.append(obj)
    return entries


def _is_tool_enabled(tool_name: str, config: dict[str, Any] | None) -> bool:
    """Check if a tool is enabled based on config filtering.

    Config supports:
        enabled: list of tool names to include (whitelist)
        disabled: list of tool names to exclude (blacklist)

    If 'enabled' is specified, only those tools are included.
    If 'disabled' is specified, those tools are excluded.
    If both are specified, 'enabled' takes precedence.
    """
    if config is None:
        return True

    enabled = config.get("enabled")
    if enabled is not None:
        return tool_name in enabled

    disabled = config.get("disabled")
    if disabled is not None:
        return tool_name not in disabled

    return True


async def expand_toolset_to_entries(
    toolset: AbstractToolset[Any],
    config: dict[str, Any] | None = None,
    run_ctx: Any = None,
) -> list[ToolsetToolEntry]:
    """Expand a toolset into individual ToolsetToolEntry instances.

    Each tool in the toolset becomes a separate entry that can
    be registered in the Context registry.

    Args:
        toolset: AbstractToolset instance
        config: Optional configuration with 'enabled'/'disabled' lists for filtering
        run_ctx: Optional RunContext to pass to get_tools (required for FunctionToolset)

    Returns:
        List of ToolsetToolEntry instances
    """
    from pydantic_ai.toolsets import FunctionToolset
    from pydantic_ai.tools import ToolDefinition

    entries: list[ToolsetToolEntry] = []

    # For FunctionToolset, we can access tools directly without get_tools()
    if isinstance(toolset, FunctionToolset):
        for tool_name, tool in toolset.tools.items():
            if not _is_tool_enabled(tool_name, config):
                continue
            # Create ToolDefinition from Tool's function_schema
            tool_def = ToolDefinition(
                name=tool.name,
                description=tool.description or tool.function_schema.description,
                parameters_json_schema=tool.function_schema.json_schema,
            )
            entries.append(ToolsetToolEntry(
                toolset=toolset,
                tool_name=tool_name,
                tool_def=tool_def,
                requires_approval=tool.requires_approval,
                _original_tool=tool,  # Preserve for schema in _collect_tools
            ))
    else:
        # For other toolsets, use get_tools() with provided context
        tools = await toolset.get_tools(run_ctx)
        for tool_name, toolset_tool in tools.items():
            if not _is_tool_enabled(tool_name, config):
                continue
            entries.append(ToolsetToolEntry(
                toolset=toolset,
                tool_name=tool_name,
                tool_def=toolset_tool.tool_def,
                requires_approval=getattr(toolset_tool, "requires_approval", False),
            ))

    return entries


def load_toolsets_from_files(files: list[str | Path]) -> dict[str, AbstractToolset[Any]]:
    """Load all toolsets from multiple Python files.

    Args:
        files: List of paths to Python files

    Returns:
        Dict mapping toolset names to instances

    Raises:
        ValueError: If duplicate toolset names are found
    """
    all_toolsets: dict[str, AbstractToolset[Any]] = {}

    for file_path in files:
        path = Path(file_path)
        if path.suffix != ".py":
            continue

        module = load_module(path)
        toolsets = discover_toolsets_from_module(module)

        for name, toolset in toolsets.items():
            if name in all_toolsets:
                raise ValueError(f"Duplicate toolset name: {name}")
            all_toolsets[name] = toolset

    return all_toolsets


def load_entries_from_files(files: list[str | Path]) -> dict[str, ToolEntry | WorkerEntry]:
    """Load all ToolEntry/WorkerEntry from multiple Python files.

    Args:
        files: List of paths to Python files

    Returns:
        Dict mapping entry names to instances
    """
    all_entries: dict[str, ToolEntry | WorkerEntry] = {}

    for file_path in files:
        path = Path(file_path)
        if path.suffix != ".py":
            continue

        module = load_module(path)
        entries = discover_entries_from_module(module)

        for entry in entries:
            all_entries[entry.name] = entry

    return all_entries
