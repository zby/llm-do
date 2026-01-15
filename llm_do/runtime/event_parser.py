"""Event parser for converting raw PydanticAI events to runtime events."""
from __future__ import annotations

from typing import Any

from .events import (
    CompletionEvent,
    DeferredToolEvent,
    ErrorEvent,
    InitialRequestEvent,
    RuntimeEvent,
    StatusEvent,
    TextResponseEvent,
    ToolCallEvent,
    ToolResultEvent,
)


def _extract_delta_content(event: Any) -> str:
    """Safely extract content delta from a PartDeltaEvent."""
    try:
        return event.delta.content_delta or ""
    except AttributeError:
        return ""


def parse_event(payload: dict[str, Any]) -> RuntimeEvent:
    """Parse a raw callback payload into a runtime event."""
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

    if "initial_request" in payload:
        req = payload["initial_request"]
        return InitialRequestEvent(
            worker=worker,
            depth=depth,
            instructions=req.get("instructions", ""),
            user_input=req.get("user_input", ""),
            attachments=req.get("attachments", []),
        )

    if "status" in payload:
        status = payload["status"]
        if isinstance(status, dict):
            return StatusEvent(
                worker=worker,
                depth=depth,
                phase=status.get("phase", ""),
                state=status.get("state", ""),
                model=status.get("model", ""),
                duration_sec=status.get("duration_sec"),
            )
        return StatusEvent(worker=worker, depth=depth, phase=str(status))

    if "error" in payload:
        error = payload["error"]
        if isinstance(error, dict):
            return ErrorEvent(
                worker=worker,
                depth=depth,
                message=error.get("message", ""),
                error_type=error.get("type", "error"),
                traceback=error.get("traceback"),
            )
        return ErrorEvent(worker=worker, depth=depth, message=str(error), error_type="error")

    if "deferred_tool" in payload:
        deferred = payload["deferred_tool"]
        return DeferredToolEvent(
            worker=worker,
            depth=depth,
            tool_name=deferred.get("tool_name", ""),
            status=deferred.get("status", "pending"),
        )

    event = payload.get("event")
    if event is None:
        return StatusEvent(worker=worker, depth=depth)

    if isinstance(event, PartStartEvent):
        if isinstance(event.part, TextPart):
            return TextResponseEvent(worker=worker, depth=depth, is_complete=False)
        return StatusEvent(worker=worker, depth=depth)

    if isinstance(event, PartDeltaEvent):
        delta = _extract_delta_content(event)
        if delta:
            return TextResponseEvent(
                worker=worker,
                depth=depth,
                content=delta,
                is_delta=True,
            )
        return StatusEvent(worker=worker, depth=depth)

    if isinstance(event, PartEndEvent):
        if isinstance(event.part, TextPart):
            return TextResponseEvent(
                worker=worker,
                depth=depth,
                content=event.part.content,
                is_complete=True,
            )
        return StatusEvent(worker=worker, depth=depth)

    if isinstance(event, (FunctionToolCallEvent, BuiltinToolCallEvent)):
        tool_part = event.part
        return ToolCallEvent(
            worker=worker,
            depth=depth,
            tool_name=getattr(tool_part, "tool_name", "tool"),
            tool_call_id=getattr(tool_part, "tool_call_id", ""),
            args=getattr(tool_part, "args", {}),
            args_json=tool_part.args_as_json_str() if hasattr(tool_part, "args_as_json_str") else "",
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
        return CompletionEvent(worker=worker, depth=depth)

    return StatusEvent(worker=worker, depth=depth)
