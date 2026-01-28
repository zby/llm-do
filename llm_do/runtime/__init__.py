"""Runtime-centric execution API for llm-do.

This module provides a runtime architecture that:
- Uses Runtime as the shared execution environment
- Supports toolsets (AbstractToolset, FunctionToolset)
- Loads tools from Python files and agent declarations
- Provides the `llm-do` CLI entry point
"""
from ..toolsets.loader import ToolsetSpec
from .agent_file import (
    AgentDefinition,
    AgentFileParser,
    # Backwards compatibility aliases (deprecated)
    WorkerDefinition,
    WorkerFileParser,
    load_agent_file,
    load_worker_file,
    parse_agent_file,
    parse_worker_file,
)
from .approval import (
    AgentApprovalPolicy,
    ApprovalCallback,
    RunApprovalPolicy,
    # Backwards compatibility alias (deprecated)
    WorkerApprovalPolicy,
    resolve_approval_callback,
)
from .args import AgentArgs, Attachment, PromptContent, PromptMessages, WorkerArgs
from .call import CallScope
from .context import CallContext
from .contracts import (
    AgentEntry,
    AgentSpec,
    Entry,
    EventCallback,
    FunctionEntry,
    ModelType,
)
from .discovery import (
    discover_agents_from_module,
    discover_toolsets_from_module,
    load_agents_from_files,
    load_all_from_files,
    load_module,
    load_toolsets_from_files,
)
from .entry_resolver import resolve_entry
from .manifest import (
    EntryConfig,
    ManifestRuntimeConfig,
    ProjectManifest,
    load_manifest,
    resolve_generated_agents_dir,
    resolve_manifest_paths,
)
from .registry import AgentRegistry, build_registry
from .runtime import Runtime

__all__ = [
    # Runtime
    "Runtime",
    "CallContext",
    "CallScope",
    "Entry",
    "FunctionEntry",
    "AgentEntry",
    "AgentSpec",
    "ModelType",
    "EventCallback",
    "ApprovalCallback",
    "RunApprovalPolicy",
    "AgentApprovalPolicy",
    "WorkerApprovalPolicy",  # Deprecated alias
    "resolve_approval_callback",
    "AgentRegistry",
    "build_registry",
    "Attachment",
    "PromptContent",
    "PromptMessages",
    "AgentArgs",
    "WorkerArgs",  # Deprecated alias
    # Agent file
    "AgentDefinition",
    "AgentFileParser",
    "parse_agent_file",
    "load_agent_file",
    # Deprecated aliases
    "WorkerDefinition",
    "WorkerFileParser",
    "parse_worker_file",
    "load_worker_file",
    # Discovery
    "load_module",
    "discover_toolsets_from_module",
    "discover_agents_from_module",
    "resolve_entry",
    "load_toolsets_from_files",
    "load_agents_from_files",
    "load_all_from_files",
    # Manifest
    "ProjectManifest",
    "ManifestRuntimeConfig",
    "EntryConfig",
    "load_manifest",
    "resolve_manifest_paths",
    "resolve_generated_agents_dir",
    # Toolset factories
    "ToolsetSpec",
]
