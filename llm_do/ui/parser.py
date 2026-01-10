"""Event parser for converting raw pydantic-ai events to typed UIEvents.

This is the single place where raw pydantic-ai event types are inspected
and converted to our typed event hierarchy.
"""
from __future__ import annotations

from typing import Any

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


def _extract_delta_content(event: Any) -> str:
    """Safely extract content delta from a PartDeltaEvent.

    PartDeltaEvent.delta varies by part type, so we use a try/except
    rather than hasattr checks for cleaner code.
    """
    try:
        return event.delta.content_delta or ""
    except AttributeError:
        return ""


def parse_event(payload: dict[str, Any]) -> UIEvent:
    """Parse a raw callback payload into a typed UIEvent.

    This is the single point where raw pydantic-ai events and
    callback dicts are converted to our typed event hierarchy.
    """
    from pydantic_ai.messages import (
        BuiltinToolCallEvent,
        BuiltinToolResultEvent,
        FinalResultEvent,
        FunctionToolCallEvent,
        FunctionToolResultEvent,
        PartDeltaEvent,
        PartEndEvent,
        PartStartEvent,
        TextPart,
    )

    worker = payload.get("worker", "worker")
    depth = payload.get("depth", 0)

    # Initial request preview
    if "initial_request" in payload:
        req = payload["initial_request"]
        return InitialRequestEvent(
            worker=worker,
            instructions=req.get("instructions", ""),
            user_input=req.get("user_input", ""),
            attachments=req.get("attachments", []),
        )

    # Status update
    if "status" in payload:
        status = payload["status"]
        if isinstance(status, dict):
            return StatusEvent(
                worker=worker,
                phase=status.get("phase", ""),
                state=status.get("state", ""),
                model=status.get("model", ""),
                duration_sec=status.get("duration_sec"),
            )
        return StatusEvent(worker=worker, phase=str(status))

    # Error event
    if "error" in payload:
        error = payload["error"]
        if isinstance(error, dict):
            return ErrorEvent(
                worker=worker,
                message=error.get("message", ""),
                error_type=error.get("type", "error"),
                traceback=error.get("traceback"),
            )
        return ErrorEvent(worker=worker, message=str(error), error_type="error")

    # Deferred tool event
    if "deferred_tool" in payload:
        deferred = payload["deferred_tool"]
        return DeferredToolEvent(
            worker=worker,
            tool_name=deferred.get("tool_name", ""),
            status=deferred.get("status", "pending"),
        )

    # PydanticAI event
    event = payload.get("event")
    if event is None:
        return StatusEvent(worker=worker)  # Fallback for unknown payloads

    if isinstance(event, PartStartEvent):
        if isinstance(event.part, TextPart):
            return TextResponseEvent(worker=worker, depth=depth, is_complete=False)
        # Tool call start is handled by FunctionToolCallEvent
        return StatusEvent(worker=worker)

    if isinstance(event, PartDeltaEvent):
        # Safely extract content delta - PartDeltaEvent.delta may vary by part type
        delta = _extract_delta_content(event)
        # Only emit TextResponseEvent for non-empty text deltas
        if delta:
            return TextResponseEvent(
                worker=worker,
                depth=depth,
                content=delta,
                is_delta=True,
            )
        # Non-text deltas (e.g., tool call parts) are ignored
        return StatusEvent(worker=worker)

    if isinstance(event, PartEndEvent):
        if isinstance(event.part, TextPart):
            return TextResponseEvent(
                worker=worker,
                depth=depth,
                content=event.part.content,
                is_complete=True,
            )
        return StatusEvent(worker=worker)

    if isinstance(event, (FunctionToolCallEvent, BuiltinToolCallEvent)):
        tool_part = event.part
        return ToolCallEvent(
            worker=worker,
            tool_name=getattr(tool_part, "tool_name", "tool"),
            tool_call_id=getattr(tool_part, "tool_call_id", ""),
            args=getattr(tool_part, "args", {}),
            args_json=tool_part.args_as_json_str() if hasattr(tool_part, "args_as_json_str") else "",
            depth=depth,
        )

    if isinstance(event, (FunctionToolResultEvent, BuiltinToolResultEvent)):
        tool_result = event.result
        return ToolResultEvent(
            worker=worker,
            depth=depth,
            tool_name=getattr(tool_result, "tool_name", "tool"),
            tool_call_id=getattr(tool_result, "tool_call_id", ""),
            content=tool_result.content if hasattr(tool_result, "content") else tool_result,
            is_error=getattr(tool_result, "is_error", False),
        )

    if isinstance(event, FinalResultEvent):
        return CompletionEvent(worker=worker)

    # Unknown event type - return empty status
    return StatusEvent(worker=worker)


def parse_approval_request(request: Any) -> ApprovalRequestEvent:
    """Parse an ApprovalRequest into an ApprovalRequestEvent.

    Args:
        request: An ApprovalRequest object from pydantic_ai_blocking_approval

    Returns:
        ApprovalRequestEvent ready for display
    """
    return ApprovalRequestEvent(
        worker="worker",
        tool_name=getattr(request, "tool_name", ""),
        reason=getattr(request, "description", ""),
        args=getattr(request, "tool_args", {}),
        request=request,
    )
