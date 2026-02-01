"""Adapter to translate runtime events into UI events."""
from __future__ import annotations

from typing import Any

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

from llm_do.runtime import events as runtime

from . import events as ui


def _extract_delta_content(event: PartDeltaEvent) -> str:
    """Safely extract content delta from a PartDeltaEvent."""
    return getattr(event.delta, "content_delta", "") or ""


def _tool_call_args_json(part: Any) -> str:
    if hasattr(part, "args_as_json_str"):
        return part.args_as_json_str()
    return ""


def adapt_event(event: runtime.RuntimeEvent) -> ui.UIEvent | None:
    """Convert a runtime event into its UI event equivalent."""
    payload = event.event

    if isinstance(payload, runtime.UserMessageEvent):
        return ui.UserMessageEvent(
            agent=event.agent,
            depth=event.depth,
            content=payload.content,
        )

    if isinstance(payload, PartStartEvent):
        if isinstance(payload.part, TextPart):
            return ui.TextResponseEvent(
                agent=event.agent,
                depth=event.depth,
                is_complete=False,
            )
        return None

    if isinstance(payload, PartDeltaEvent):
        delta = _extract_delta_content(payload)
        if delta:
            return ui.TextResponseEvent(
                agent=event.agent,
                depth=event.depth,
                content=delta,
                is_delta=True,
            )
        return None

    if isinstance(payload, PartEndEvent):
        if isinstance(payload.part, TextPart):
            return ui.TextResponseEvent(
                agent=event.agent,
                depth=event.depth,
                content=payload.part.content,
                is_complete=True,
            )
        return None

    if isinstance(payload, (FunctionToolCallEvent, BuiltinToolCallEvent)):
        tool_part = payload.part
        return ui.ToolCallEvent(
            agent=event.agent,
            depth=event.depth,
            tool_name=getattr(tool_part, "tool_name", "tool"),
            tool_call_id=getattr(tool_part, "tool_call_id", ""),
            args=getattr(tool_part, "args", {}),
            args_json=_tool_call_args_json(tool_part),
        )

    if isinstance(payload, (FunctionToolResultEvent, BuiltinToolResultEvent)):
        tool_result = payload.result
        return ui.ToolResultEvent(
            agent=event.agent,
            depth=event.depth,
            tool_name=getattr(tool_result, "tool_name", "tool"),
            tool_call_id=getattr(tool_result, "tool_call_id", ""),
            content=tool_result.content if hasattr(tool_result, "content") else tool_result,
            is_error=getattr(tool_result, "is_error", False),
        )

    if isinstance(payload, FinalResultEvent):
        return ui.CompletionEvent(agent=event.agent, depth=event.depth)

    return None
