"""PydanticAI-based runtime for llm-do workers."""
from __future__ import annotations

from pydantic_ai_blocking_approval import ApprovalController, ApprovalDecision

from .base import (
    AgentRunner,
    AttachmentPayload,
    DeferredApprovalHandler,
    DeferredCallHandler,
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
    run_worker_async,
    run_worker_with_deferred_async,
)
from .model_compat import (
    InvalidCompatibleModelsError,
    ModelCompatibilityError,
    NoModelError,
)
from .sandbox import AttachmentPolicy

__all__ = [
    "AgentRunner",
    "ApprovalController",
    "ApprovalDecision",
    "AttachmentPayload",
    "AttachmentPolicy",
    "DeferredApprovalHandler",
    "DeferredCallHandler",
    "InvalidCompatibleModelsError",
    "ModelCompatibilityError",
    "NoModelError",
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
    "run_worker_async",
    "run_worker_with_deferred_async",
    "__version__",
]

__version__ = "0.2.0"
