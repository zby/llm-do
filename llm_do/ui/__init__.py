"""UI components for llm-do CLI."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .display import (
    DisplayBackend,
    HeadlessDisplayBackend,
    RichDisplayBackend,
    TextualDisplayBackend,
)
from .events import (
    ApprovalRequestEvent,
    CompletionEvent,
    DeferredToolEvent,
    ErrorEvent,
    InitialRequestEvent,
    StatusEvent,
    TextResponseEvent,
    ToolCallEvent,
    ToolResultEvent,
    UIEvent,
)
from .parser import parse_approval_request, parse_event

if TYPE_CHECKING:
    from .runner import RunUiResult, run_headless, run_tui, run_ui

__all__ = [
    # Display backends
    "DisplayBackend",
    "HeadlessDisplayBackend",
    "RichDisplayBackend",
    "TextualDisplayBackend",
    # Event types
    "ApprovalRequestEvent",
    "CompletionEvent",
    "DeferredToolEvent",
    "ErrorEvent",
    "InitialRequestEvent",
    "StatusEvent",
    "TextResponseEvent",
    "ToolCallEvent",
    "ToolResultEvent",
    "UIEvent",
    # Parser
    "parse_approval_request",
    "parse_event",
    # Runners
    "RunUiResult",
    "run_headless",
    "run_tui",
    "run_ui",
]


def __getattr__(name: str):
    if name in {"RunUiResult", "run_headless", "run_tui", "run_ui"}:
        from . import runner

        return getattr(runner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
