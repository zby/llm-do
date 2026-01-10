"""Runtime-centric execution API for llm-do.

This module provides a runtime architecture that:
- Uses Runtime as the shared execution environment
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
from .args import PromptSpec, WorkerArgs, WorkerInput
from .contracts import EventCallback, Invocable, ModelType
from .deps import ToolsProxy, WorkerRuntime
from .discovery import (
    discover_toolsets_from_module,
    discover_workers_from_module,
    load_module,
    load_toolsets_from_files,
    load_workers_from_files,
)
from .registry import InvocableRegistry, build_invocable_registry
from .shared import Runtime
from .worker import ToolInvocable, Worker
from .worker_file import (
    WorkerDefinition,
    WorkerFileParser,
    load_worker_file,
    parse_worker_file,
)

__all__ = [
    # Runtime
    "Runtime",
    "WorkerRuntime",
    "ToolsProxy",
    "Invocable",
    "ModelType",
    "EventCallback",
    "ApprovalCallback",
    "RunApprovalPolicy",
    "WorkerApprovalPolicy",
    "resolve_approval_callback",
    "InvocableRegistry",
    "build_invocable_registry",
    "PromptSpec",
    "WorkerArgs",
    "WorkerInput",
    # Entries
    "Worker",
    "ToolInvocable",
    # Worker file
    "WorkerDefinition",
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
