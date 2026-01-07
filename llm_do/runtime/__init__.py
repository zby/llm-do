"""WorkerRuntime-centric runtime for llm-do.

This module provides a new runtime architecture that:
- Uses WorkerRuntime as the central dispatcher
- Supports toolsets (AbstractToolset, FunctionToolset)
- Loads tools from Python files and worker declarations
- Provides the `llm-do` CLI entry point
"""
from .approval import (
    ApprovalCallback,
    RunApprovalPolicy,
    WorkerApprovalPolicy,
    resolve_approval_callback,
)
from .context import ToolsProxy, WorkerRuntime
from .contracts import EventCallback, Invocable, ModelType
from .discovery import (
    discover_toolsets_from_module,
    discover_workers_from_module,
    load_module,
    load_toolsets_from_files,
    load_workers_from_files,
)
from .runner import run_invocable
from .worker import ToolInvocable, Worker
from .worker_file import (
    WorkerDefinition,
    WorkerFile,  # Backward compatibility alias
    WorkerFileParser,
    load_worker_file,
    parse_worker_file,
)

__all__ = [
    # Runtime
    "WorkerRuntime",
    "ToolsProxy",
    "Invocable",
    "ModelType",
    "EventCallback",
    "ApprovalCallback",
    "RunApprovalPolicy",
    "WorkerApprovalPolicy",
    "resolve_approval_callback",
    "run_invocable",
    # Entries
    "Worker",
    "ToolInvocable",
    # Worker file
    "WorkerDefinition",
    "WorkerFile",  # Backward compatibility alias
    "WorkerFileParser",
    "parse_worker_file",
    "load_worker_file",
    # Discovery
    "load_module",
    "discover_toolsets_from_module",
    "discover_workers_from_module",
    "load_toolsets_from_files",
    "load_workers_from_files",
]
