"""Toolset implementations shipped with llm-do."""

from typing import TYPE_CHECKING, Any

from .filesystem import FileSystemToolset, ReadOnlyFileSystemToolset
from .shell import ShellToolset

if TYPE_CHECKING:
    from .dynamic_agents import DynamicAgentsToolset


def __getattr__(name: str) -> Any:
    if name == "DynamicAgentsToolset":
        from .dynamic_agents import DynamicAgentsToolset

        return DynamicAgentsToolset
    raise AttributeError(name)


__all__ = [
    "DynamicAgentsToolset",
    "FileSystemToolset",
    "ReadOnlyFileSystemToolset",
    "ShellToolset",
]
