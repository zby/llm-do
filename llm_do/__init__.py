"""PydanticAI-based runtime for llm-do workers."""
from __future__ import annotations

from .base import (
    AgentRunner,
    ApprovalCallback,
    ApprovalController,
    ApprovalDecision,
    AttachmentPayload,
    RuntimeCreator,
    RuntimeDelegator,
    WorkerContext,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRegistry,
    WorkerRunResult,
    WorkerSpec,
    approve_all_callback,
    call_worker,
    create_worker,
    run_worker,
    strict_mode_callback,
)
from .sandbox import AttachmentPolicy

__all__ = [
    "AgentRunner",
    "ApprovalCallback",
    "ApprovalController",
    "ApprovalDecision",
    "approve_all_callback",
    "strict_mode_callback",
    "AttachmentPayload",
    "AttachmentPolicy",
    "RuntimeCreator",
    "RuntimeDelegator",
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
