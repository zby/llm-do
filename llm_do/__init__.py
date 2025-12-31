"""llm-do: LLM-powered worker runtime.

This package provides the context-centric runtime for LLM workers.

Main entry points:
- llm-do CLI: Run workers from .worker and .py files
- ctx_runtime module: Programmatic API for running workers

Security model: llm-do is designed to run inside a Docker container.
The container provides the security boundary. Running on bare metal
is at user's own risk.
"""
from __future__ import annotations

from pydantic_ai_blocking_approval import (
    ApprovalBlocked,
    ApprovalCallback,
    ApprovalDecision,
    ApprovalDenied,
    ApprovalError,
    ApprovalRequest,
    ApprovalResult,
    ApprovalToolset,
)

from .model_compat import (
    InvalidCompatibleModelsError,
    ModelCompatibilityError,
    NoModelError,
)

# Re-export from ctx_runtime for convenience
from .ctx_runtime import Context, WorkerEntry, ToolEntry

__all__ = [
    # Approval handling
    "ApprovalBlocked",
    "ApprovalCallback",
    "ApprovalDecision",
    "ApprovalDenied",
    "ApprovalError",
    "ApprovalRequest",
    "ApprovalResult",
    "ApprovalToolset",
    # Model errors
    "InvalidCompatibleModelsError",
    "ModelCompatibilityError",
    "NoModelError",
    # Runtime types
    "Context",
    "WorkerEntry",
    "ToolEntry",
    # Version
    "__version__",
]

__version__ = "0.3.0"
