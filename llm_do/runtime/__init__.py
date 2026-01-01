"""WorkerRuntime-centric runtime for llm-do.

This module provides a new runtime architecture that:
- Uses WorkerRuntime as the central dispatcher
- Supports toolsets (AbstractToolset, FunctionToolset)
- Loads tools from Python files and worker declarations
- Provides the `llm-do` CLI entry point
"""
from .approval import ApprovalPolicy, wrap_entry_for_approval
from .context import Invocable, ModelType, ToolsProxy, WorkerRuntime
from .discovery import (
    discover_toolsets_from_module,
    discover_workers_from_module,
    load_module,
    load_toolsets_from_files,
    load_workers_from_files,
)
from .worker import ToolInvocable, Worker

from llm_do.toolsets.builtins import BUILTIN_TOOLSETS, get_builtin_toolset
from .runner import run_entry
from .worker_file import WorkerFile, load_worker_file, parse_worker_file

__all__ = [
    # Runtime
    "WorkerRuntime",
    "ToolsProxy",
    "Invocable",
    "ModelType",
    "ApprovalPolicy",
    "wrap_entry_for_approval",
    "run_entry",
    # Entries
    "Worker",
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
    # Builtins
    "BUILTIN_TOOLSETS",
    "get_builtin_toolset",
]
