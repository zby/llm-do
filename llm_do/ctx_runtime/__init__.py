"""Context-centric runtime for llm-do.

This module provides a new runtime architecture that:
- Uses Context as the central dispatcher
- Supports toolsets (AbstractToolset, FunctionToolset)
- Loads tools from Python files and worker declarations
- Provides the `llm-do` CLI entry point
"""
from .ctx import Context, ToolsProxy, CallableEntry, ApprovalFn, ModelType
from .entries import WorkerEntry, ToolEntry
from .worker_file import WorkerFile, parse_worker_file, load_worker_file
from .discovery import (
    load_module,
    discover_toolsets_from_module,
    discover_entries_from_module,
    load_toolsets_from_files,
    load_entries_from_files,
)
from .builtins import BUILTIN_TOOLSETS, get_builtin_toolset

__all__ = [
    # Context
    "Context",
    "ToolsProxy",
    "CallableEntry",
    "ApprovalFn",
    "ModelType",
    # Entries
    "WorkerEntry",
    "ToolEntry",
    # Worker file
    "WorkerFile",
    "parse_worker_file",
    "load_worker_file",
    # Discovery
    "load_module",
    "discover_toolsets_from_module",
    "discover_entries_from_module",
    "load_toolsets_from_files",
    "load_entries_from_files",
    # Builtins
    "BUILTIN_TOOLSETS",
    "get_builtin_toolset",
]
