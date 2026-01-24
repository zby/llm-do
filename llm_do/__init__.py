"""llm-do: LLM-powered entry runtime.

This package provides the runtime for LLM entries.

Main entry points:
- llm-do CLI: Run entries from .worker and .py files
- runtime module: Programmatic API for running entries

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

from .models import (
    InvalidCompatibleModelsError,
    ModelCompatibilityError,
    NoModelError,
)

# Re-export from runtime for convenience
from .runtime import AgentEntry, CallRuntime, Runtime

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
    "CallRuntime",
    "Runtime",
    "AgentEntry",
    # Version
    "__version__",
]

__version__ = "0.3.0"
