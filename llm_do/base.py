"""Foundational PydanticAI-based runtime for llm-do.

This module provides:

- Worker artifacts (definition/spec/defaults) with YAML/JSON persistence via
  ``WorkerRegistry``.
- Runtime orchestration through ``run_worker`` using PydanticAI agents.
- Sandbox-aware filesystem helpers with optional approval gating.
- Worker delegation and creation tools that honor allowlists and locks.

The design favors testability and deterministic enforcement through pluggable
agent runners and approval callbacks.

This module serves as a re-export layer. The actual implementations are in:
- types.py: Data models and type definitions
- registry.py: WorkerRegistry implementation
- runtime.py: Async runtime core and execution logic
"""
from __future__ import annotations

from typing import Iterable

# Re-export sandbox types
from .sandbox import AttachmentInput, AttachmentPayload, AttachmentPolicy

# Re-export sandbox types from standalone package
from pydantic_ai_filesystem_sandbox import (
    DEFAULT_MAX_READ_CHARS,
    SandboxConfig as BaseSandboxConfig,
    SandboxError,
    Sandbox as BaseSandbox,
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
    InvocationMode,
    MessageCallback,
    ModelLike,
    OutputSchemaResolver,
    ProgramConfig,
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

# Re-export program module
from .program import (
    InvalidProgramError,
    ProgramContext,
    resolve_program,
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
from .protocols import FileSandbox

# Tools are now provided via toolsets in execution.py:
# - FileSystemToolset (wrapped with ApprovalToolset), ShellToolset, DelegationToolset, CustomToolset

# Re-export runtime functions
from .runtime import (
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
    # Program types (worker-function architecture)
    "InvocationMode",
    "InvalidProgramError",
    "ProgramConfig",
    "ProgramContext",
    "resolve_program",
    # Protocols
    "FileSandbox",
    # Sandbox classes
    "DEFAULT_MAX_READ_CHARS",
    "BaseSandboxConfig",
    "SandboxError",
    "BaseSandbox",
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
