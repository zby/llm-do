"""Runtime-centric execution API for llm-do.

This module provides a runtime architecture that:
- Uses Runtime as the shared execution environment
- Supports toolsets (AbstractToolset, FunctionToolset)
- Loads tools from Python files and worker declarations
- Provides the `llm-do` CLI entry point
"""
from ..toolsets.loader import ToolsetBuildContext, ToolsetSpec
from .approval import (
    ApprovalCallback,
    RunApprovalPolicy,
    WorkerApprovalPolicy,
    resolve_approval_callback,
)
from .args import Attachment, PromptContent, PromptMessages, WorkerArgs
from .call import CallScope
from .contracts import AgentSpec, EntrySpec, EventCallback, ModelType
from .deps import WorkerRuntime
from .discovery import (
    discover_agents_from_module,
    discover_entries_from_module,
    discover_toolsets_from_module,
    load_agents_from_files,
    load_all_from_files,
    load_module,
    load_toolsets_from_files,
)
from .manifest import (
    EntryConfig,
    ManifestRuntimeConfig,
    ProjectManifest,
    load_manifest,
    resolve_manifest_paths,
)
from .registry import AgentRegistry, build_entry
from .shared import Runtime
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
    "CallScope",
    "EntrySpec",
    "AgentSpec",
    "ModelType",
    "EventCallback",
    "ApprovalCallback",
    "RunApprovalPolicy",
    "WorkerApprovalPolicy",
    "resolve_approval_callback",
    "AgentRegistry",
    "build_entry",
    "Attachment",
    "PromptContent",
    "PromptMessages",
    "WorkerArgs",
    # Worker file
    "WorkerDefinition",
    "WorkerFileParser",
    "parse_worker_file",
    "load_worker_file",
    # Discovery
    "load_module",
    "discover_toolsets_from_module",
    "discover_agents_from_module",
    "discover_entries_from_module",
    "load_toolsets_from_files",
    "load_agents_from_files",
    "load_all_from_files",
    # Manifest
    "ProjectManifest",
    "ManifestRuntimeConfig",
    "EntryConfig",
    "load_manifest",
    "resolve_manifest_paths",
    # Toolset factories
    "ToolsetBuildContext",
    "ToolsetSpec",
]
