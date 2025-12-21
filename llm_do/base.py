"""Foundational PydanticAI-based runtime for llm-do.

This module provides:

- Worker artifacts (definition/spec/defaults) with YAML/JSON persistence via
  ``WorkerRegistry``.
- Runtime orchestration through ``run_worker_async`` using PydanticAI agents.
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

# Re-export attachment types
from .attachments import AttachmentInput, AttachmentPayload, AttachmentPolicy

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

# Tools are now provided via toolsets in execution.py:
# - FileSystemToolset (wrapped with ApprovalToolset), ShellToolset, AgentToolset, CustomToolset

# Re-export runtime functions
from .runtime import (
    call_worker_async,
    create_worker,
    run_tool_async,
    run_worker_async,
)
from .tool_context import tool_context

__all__: Iterable[str] = [
    "AgentRunner",
    "AttachmentPayload",
    "ApprovalController",
    "ApprovalDecision",
    "AttachmentPolicy",
    "WorkerDefinition",
    "WorkerSpec",
    "WorkerCreationDefaults",
    "WorkerRegistry",
    "WorkerRunResult",
    "run_tool_async",
    "run_worker_async",
    "call_worker_async",
    "create_worker",
    "WorkerContext",
    "tool_context",
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
