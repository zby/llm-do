"""UI components for llm-do CLI."""
from __future__ import annotations

from .adapter import adapt_event
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
from .parser import parse_approval_request

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
    # Adapter
    "adapt_event",
]
