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
from pydantic_ai_filesystem_sandbox import (
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
    MessageCallback,
    ModelLike,
    OutputSchemaResolver,
    ServerSideToolConfig,
    ShellDefault,
    ShellResult,
    ShellRule,
    WorkerContext,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRunResult,
    WorkerSpec,
)

# Re-export approval types from standalone package
from pydantic_ai_blocking_approval import ApprovalController, ApprovalDecision

# Re-export shell module
from .shell import (
    ShellBlockedError,
    ShellError,
    execute_shell,
    match_shell_rules,
)

# Re-export registry
from .registry import WorkerRegistry

# Re-export protocols
from .protocols import FileSandbox, WorkerCreator, WorkerDelegator

# Tools are now provided via toolsets in execution.py:
# - FileSandboxApprovalToolset, ShellApprovalToolset, DelegationApprovalToolset, CustomApprovalToolset

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
    "ApprovalController",
    "ApprovalDecision",
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
    # Server-side tools
    "ServerSideToolConfig",
]
