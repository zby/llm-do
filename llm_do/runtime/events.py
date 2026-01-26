"""Runtime event types emitted by the core execution layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeEvent:
    """Base event for runtime callbacks (no rendering concerns)."""

    worker: str = ""  # Note: "worker" field name kept for backwards compatibility; represents agent name
    depth: int = 0


@dataclass
class InitialRequestEvent(RuntimeEvent):
    instructions: str = ""
    user_input: str = ""
    attachments: list[str] = field(default_factory=list)


@dataclass
class StatusEvent(RuntimeEvent):
    phase: str = ""
    state: str = ""
    model: str = ""
    duration_sec: float | None = None


@dataclass
class UserMessageEvent(RuntimeEvent):
    content: str = ""


@dataclass
class TextResponseEvent(RuntimeEvent):
    content: str = ""
    is_complete: bool = True
    is_delta: bool = False


@dataclass
class ToolCallEvent(RuntimeEvent):
    tool_name: str = ""
    tool_call_id: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    args_json: str = ""


@dataclass
class ToolResultEvent(RuntimeEvent):
    tool_name: str = ""
    tool_call_id: str = ""
    content: Any = ""
    is_error: bool = False


@dataclass
class DeferredToolEvent(RuntimeEvent):
    tool_name: str = ""
    status: str = ""


@dataclass
class CompletionEvent(RuntimeEvent):
    """Event emitted when a run completes."""


@dataclass
class ErrorEvent(RuntimeEvent):
    message: str = ""
    error_type: str = ""
    traceback: str | None = None
