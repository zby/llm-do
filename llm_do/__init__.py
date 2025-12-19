"""PydanticAI-based runtime for llm-do workers.

Security model: llm-do is designed to run inside a Docker container.
The container provides the security boundary. Running on bare metal
is at user's own risk.
"""
from __future__ import annotations

from pydantic_ai_blocking_approval import ApprovalController, ApprovalDecision

from .base import (
    AgentRunner,
    AttachmentPayload,
    ServerSideToolConfig,
    WorkerContext,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRegistry,
    WorkerRunResult,
    WorkerSpec,
    call_worker_async,
    create_worker,
    run_worker_async,
)
from .model_compat import (
    InvalidCompatibleModelsError,
    ModelCompatibilityError,
    NoModelError,
)
from .attachments import AttachmentPolicy

__all__ = [
    "AgentRunner",
    "ApprovalController",
    "ApprovalDecision",
    "AttachmentPayload",
    "AttachmentPolicy",
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
    "call_worker_async",
    "create_worker",
    "run_worker_async",
    "__version__",
]

__version__ = "0.2.0"
