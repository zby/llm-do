"""Foundational PydanticAI-based runtime for llm-do.

This module provides:

- Worker artifacts (definition/spec/defaults) with YAML/JSON persistence via
  ``WorkerRegistry``.
- Runtime orchestration through ``run_worker`` using PydanticAI agents.
- Sandbox-aware filesystem helpers with optional approval gating.
- Worker delegation and creation tools that honor allowlists and locks.

The design favors testability and deterministic enforcement through pluggable
agent runners and approval callbacks.

This module now serves as a backward-compatible re-export layer. The actual
implementations are in:
- types.py: Data models and type definitions
- registry.py: WorkerRegistry implementation
- runtime.py: Async runtime core and execution logic
"""
from __future__ import annotations

from typing import Iterable

# Re-export sandbox types (legacy)
from .sandbox import AttachmentInput, AttachmentPayload, AttachmentPolicy, SandboxConfig, SandboxManager, SandboxToolset

# Re-export new sandbox types
from .file_sandbox import (
    FileSandboxConfig,
    FileSandboxError,
    FileSandboxImpl,
    FileTooLargeError,
    PathConfig,
    PathNotInSandboxError,
    PathNotWritableError,
    SuffixNotAllowedError,
)
from .sandbox_v2 import Sandbox, SandboxConfig as NewSandboxConfig, sandbox_config_from_legacy

# Re-export all types
from .types import (
    AgentExecutionContext,
    AgentRunner,
    ApprovalCallback,
    ApprovalDecision,
    MessageCallback,
    ModelLike,
    OutputSchemaResolver,
    ToolRule,
    WorkerContext,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRunResult,
    WorkerSpec,
    approve_all_callback,
    strict_mode_callback,
)

# Re-export registry
from .registry import WorkerRegistry

# Re-export approval
from .approval import ApprovalController

# Re-export protocols
from .protocols import FileSandbox, WorkerCreator, WorkerDelegator

# Re-export tools
from .tools import load_custom_tools, register_worker_tools

# Re-export runtime functions and implementations
from .runtime import (
    RuntimeCreator,
    RuntimeDelegator,
    call_worker,
    call_worker_async,
    create_worker,
    run_worker,
    run_worker_async,
)

__all__: Iterable[str] = [
    "AgentRunner",
    "AttachmentPayload",
    "ApprovalCallback",
    "ApprovalController",
    "ApprovalDecision",
    "approve_all_callback",
    "strict_mode_callback",
    "AttachmentPolicy",
    "ToolRule",
    "SandboxConfig",
    "WorkerDefinition",
    "WorkerSpec",
    "WorkerCreationDefaults",
    "WorkerRegistry",
    "WorkerRunResult",
    "run_worker",
    "run_worker_async",
    "call_worker",
    "call_worker_async",
    "create_worker",
    "SandboxManager",
    "SandboxToolset",
    "WorkerContext",
    # Protocols
    "FileSandbox",
    "WorkerCreator",
    "WorkerDelegator",
    # Protocol implementations
    "RuntimeCreator",
    "RuntimeDelegator",
    # Tools
    "load_custom_tools",
    "register_worker_tools",
    # New sandbox classes
    "FileSandboxConfig",
    "FileSandboxError",
    "FileSandboxImpl",
    "FileTooLargeError",
    "NewSandboxConfig",
    "PathConfig",
    "PathNotInSandboxError",
    "PathNotWritableError",
    "Sandbox",
    "SuffixNotAllowedError",
    "sandbox_config_from_legacy",
]
