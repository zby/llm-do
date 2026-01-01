"""Built-in toolset registry.

This module provides BUILTIN_TOOLSETS, a dict mapping toolset names
to their classes. Worker files can reference these by name.

Built-in toolsets:
- shell: Execute shell commands with pattern-based approval
- filesystem: Read/write files and list directories
"""
from __future__ import annotations

from typing import Any, Protocol

from pydantic_ai.toolsets import AbstractToolset

from llm_do.toolsets.filesystem import FileSystemToolset
from llm_do.toolsets.shell import ShellToolset


class ToolsetFactory(Protocol):
    def __call__(self, config: dict[str, Any]) -> AbstractToolset[Any]: ...

BUILTIN_TOOLSETS: dict[str, ToolsetFactory] = {
    "shell": ShellToolset,
    "filesystem": FileSystemToolset,
}


def get_builtin_toolset(
    name: str, config: dict[str, Any]
) -> tuple[AbstractToolset[Any], dict[str, dict[str, Any]]]:
    """Get a built-in toolset instance by name.

    Args:
        name: Toolset name (e.g., "shell", "filesystem")
        config: Configuration dict for the toolset

    Returns:
        Tuple of (toolset, approval_config) where approval_config is
        a dict mapping tool names to their approval settings

    Raises:
        KeyError: If name is not a known built-in
    """
    if name not in BUILTIN_TOOLSETS:
        raise KeyError(f"Unknown built-in toolset: {name}. Available: {list(BUILTIN_TOOLSETS.keys())}")

    # Copy config to avoid mutation
    config = dict(config) if config else {}

    # Extract approval config (for toolsets without needs_approval or for overrides)
    approval_config = config.pop("_approval_config", {})

    toolset_class = BUILTIN_TOOLSETS[name]
    return toolset_class(config=config), approval_config
