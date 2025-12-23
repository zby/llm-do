"""Built-in toolset registry.

This module provides BUILTIN_TOOLSETS, a dict mapping toolset names
to their classes. Worker files can reference these by name.

Built-in toolsets:
- shell: Execute shell commands with pattern-based approval
- filesystem: Read/write files and list directories
"""
from __future__ import annotations

from typing import Any, Type

from pydantic_ai.toolsets import AbstractToolset

from llm_do.shell.toolset import ShellToolset
from llm_do.filesystem_toolset import FileSystemToolset


BUILTIN_TOOLSETS: dict[str, Type[AbstractToolset[Any]]] = {
    "shell": ShellToolset,
    "filesystem": FileSystemToolset,
}


def get_builtin_toolset(name: str, config: dict[str, Any]) -> AbstractToolset[Any]:
    """Get a built-in toolset instance by name.

    Args:
        name: Toolset name (e.g., "shell", "filesystem")
        config: Configuration dict for the toolset

    Returns:
        Instantiated toolset

    Raises:
        KeyError: If name is not a known built-in
    """
    if name not in BUILTIN_TOOLSETS:
        raise KeyError(f"Unknown built-in toolset: {name}. Available: {list(BUILTIN_TOOLSETS.keys())}")

    toolset_class = BUILTIN_TOOLSETS[name]
    return toolset_class(config=config)
