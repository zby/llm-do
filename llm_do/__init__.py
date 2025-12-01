"""PydanticAI-based runtime for llm-do workers."""
from __future__ import annotations

from pydantic_ai_blocking_approval import ApprovalController, ApprovalDecision

from .base import (
    AgentRunner,
    AttachmentPayload,
    RuntimeCreator,
    RuntimeDelegator,
    ServerSideToolConfig,
    WorkerContext,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRegistry,
    WorkerRunResult,
    WorkerSpec,
    call_worker,
    create_worker,
    run_worker,
)
from .sandbox import AttachmentPolicy

__all__ = [
    "AgentRunner",
    "ApprovalController",
    "ApprovalDecision",
    "AttachmentPayload",
    "AttachmentPolicy",
    "RuntimeCreator",
    "RuntimeDelegator",
    "ServerSideToolConfig",
    "WorkerContext",
    "WorkerCreationDefaults",
    "WorkerDefinition",
    "WorkerRegistry",
    "WorkerRunResult",
    "WorkerSpec",
    "call_worker",
    "create_worker",
    "run_worker",
    "__version__",
]

__version__ = "0.2.0"
