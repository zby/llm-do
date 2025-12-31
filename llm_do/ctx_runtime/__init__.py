"""Context-centric runtime for llm-do.

This module provides a new runtime architecture that:
- Uses Context as the central dispatcher
- Supports toolsets (AbstractToolset, FunctionToolset)
- Loads tools from Python files and worker declarations
- Provides the `llm-do` CLI entry point
"""
from .ctx import Context, ToolsProxy, Invocable, ModelType
from .invocables import WorkerInvocable, ToolInvocable
from .worker_file import WorkerFile, parse_worker_file, load_worker_file
from .discovery import (
    load_module,
    discover_toolsets_from_module,
    discover_workers_from_module,
    load_toolsets_from_files,
    load_workers_from_files,
)
from ..toolset_loader import (
    BUILTIN_TOOLSET_ALIASES,
    ToolsetBuildContext,
    build_toolsets,
)

__all__ = [
    # Context
    "Context",
    "ToolsProxy",
    "Invocable",
    "ModelType",
    # Entries
    "WorkerInvocable",
    "ToolInvocable",
    # Worker file
    "WorkerFile",
    "parse_worker_file",
    "load_worker_file",
    # Discovery
    "load_module",
    "discover_toolsets_from_module",
    "discover_workers_from_module",
    "load_toolsets_from_files",
    "load_workers_from_files",
    # Toolset loader
    "BUILTIN_TOOLSET_ALIASES",
    "ToolsetBuildContext",
    "build_toolsets",
]
