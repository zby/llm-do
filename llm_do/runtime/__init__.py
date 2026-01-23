"""Runtime-centric execution API for llm-do.

This module provides a runtime architecture that:
- Uses AgentRuntime as the PydanticAI deps object for agent execution
- Supports toolsets (AbstractToolset, FunctionToolset)
- Loads agents from worker files and Python files
- Provides the `llm-do` CLI entry point
"""
from ..toolsets.loader import ToolsetBuildContext, ToolsetSpec
from .agent_loader import AgentBundle, build_prompt_for_input, load_agents
from .agent_runtime import (
    AgentRuntime,
    ApprovalWrapper,
    AttachmentResolver,
    EventCallback,
    MessageAccumulator,
    MessageLogCallback,
    ToolsetResolver,
    UsageCollector,
    build_path_map,
)
from .approval import (
    ApprovalCallback,
    RunApprovalPolicy,
    resolve_approval_callback,
)
from .args import PromptSpec, WorkerArgs, WorkerInput
from .discovery import (
    discover_toolsets_from_module,
    load_all_from_files,
    load_module,
    load_toolsets_from_files,
)
from .executor import build_runtime, run, run_agent, run_entry_agent, run_sync
from .manifest import (
    EntryConfig,
    ManifestRuntimeConfig,
    ProjectManifest,
    load_manifest,
    resolve_manifest_paths,
)
from .worker_file import (
    WorkerDefinition,
    WorkerFileParser,
    load_worker_file,
    parse_worker_file,
)

__all__ = [
    # AgentRuntime (primary runtime)
    "AgentRuntime",
    "AttachmentResolver",
    "ToolsetResolver",
    "ApprovalWrapper",
    "UsageCollector",
    "MessageAccumulator",
    "EventCallback",
    "MessageLogCallback",
    "build_path_map",
    # Agent loading
    "AgentBundle",
    "load_agents",
    "build_prompt_for_input",
    # Execution
    "run",
    "run_sync",
    "run_agent",
    "run_entry_agent",
    "build_runtime",
    # Approval
    "ApprovalCallback",
    "RunApprovalPolicy",
    "resolve_approval_callback",
    # Args
    "PromptSpec",
    "WorkerArgs",
    "WorkerInput",
    # Worker file
    "WorkerDefinition",
    "WorkerFileParser",
    "parse_worker_file",
    "load_worker_file",
    # Discovery
    "load_module",
    "discover_toolsets_from_module",
    "load_toolsets_from_files",
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
