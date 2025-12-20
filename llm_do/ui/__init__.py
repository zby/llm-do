"""UI components for llm-do CLI."""
from .display import (
    DisplayBackend,
    HeadlessDisplayBackend,
    JsonDisplayBackend,
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

__all__ = [
    # Display backends
    "DisplayBackend",
    "HeadlessDisplayBackend",
    "JsonDisplayBackend",
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
]
