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
from .sandbox import AttachmentInput, AttachmentPayload, AttachmentPolicy

# Re-export new sandbox types
from .filesystem_sandbox import (
    DEFAULT_MAX_READ_CHARS,
    FileSandboxConfig,
    FileSandboxError,
    FileSandboxImpl,
    FileTooLargeError,
    PathConfig,
    PathNotInSandboxError,
    PathNotWritableError,
    ReadResult,
    SuffixNotAllowedError,
)
from .worker_sandbox import Sandbox, SandboxConfig

# Re-export all types
from .types import (
    AgentExecutionContext,
    AgentRunner,
    ApprovalCallback,
    ApprovalDecision,
    MessageCallback,
    ModelLike,
    OutputSchemaResolver,
    ShellDefault,
    ShellResult,
    ShellRule,
    WorkerContext,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRunResult,
    WorkerSpec,
    approve_all_callback,
    strict_mode_callback,
)

# Re-export shell module
from .shell import (
    ShellBlockedError,
    ShellError,
    execute_shell,
    match_shell_rules,
)

# Re-export registry
from .registry import WorkerRegistry

# Re-export approval types from unified module
from .tool_approval import ApprovalController

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
    "DEFAULT_MAX_READ_CHARS",
    "FileSandboxConfig",
    "FileSandboxError",
    "FileSandboxImpl",
    "FileTooLargeError",
    "PathConfig",
    "PathNotInSandboxError",
    "PathNotWritableError",
    "ReadResult",
    "Sandbox",
    "SuffixNotAllowedError",
    # Shell tool
    "ShellBlockedError",
    "ShellDefault",
    "ShellError",
    "ShellResult",
    "ShellRule",
    "execute_shell",
    "match_shell_rules",
]
