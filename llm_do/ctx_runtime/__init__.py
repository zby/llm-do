"""Context-centric runtime for llm-do.

This module provides a new runtime architecture that:
- Uses Context as the central dispatcher
- Supports toolsets (AbstractToolset, FunctionToolset)
- Loads tools from Python files and worker declarations
- Provides the `llm-run` CLI entry point
"""
from .ctx import Context, CallTrace, ToolsProxy, CallableEntry, ApprovalFn, ModelType
from .registry import Registry
from .entries import ToolEntry, WorkerEntry, ToolsetToolEntry, tool_entry
from .worker_file import WorkerFile, parse_worker_file, load_worker_file
from .discovery import (
    load_module,
    discover_toolsets_from_module,
    discover_entries_from_module,
    expand_toolset_to_entries,
    load_toolsets_from_files,
    load_entries_from_files,
)
from .builtins import BUILTIN_TOOLSETS, get_builtin_toolset

__all__ = [
    # Context
    "Context",
    "CallTrace",
    "ToolsProxy",
    "CallableEntry",
    "ApprovalFn",
    "ModelType",
    # Registry
    "Registry",
    # Entries
    "ToolEntry",
    "WorkerEntry",
    "ToolsetToolEntry",
    "tool_entry",
    # Worker file
    "WorkerFile",
    "parse_worker_file",
    "load_worker_file",
    # Discovery
    "load_module",
    "discover_toolsets_from_module",
    "discover_entries_from_module",
    "expand_toolset_to_entries",
    "load_toolsets_from_files",
    "load_entries_from_files",
    # Builtins
    "BUILTIN_TOOLSETS",
    "get_builtin_toolset",
]
