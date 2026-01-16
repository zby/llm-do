"""Adapter to translate runtime events into UI events."""
from __future__ import annotations

from llm_do.runtime import events as runtime

from . import events as ui


def adapt_event(event: runtime.RuntimeEvent) -> ui.UIEvent:
    """Convert a runtime event into its UI event equivalent."""
    if isinstance(event, runtime.InitialRequestEvent):
        return ui.InitialRequestEvent(
            worker=event.worker,
            depth=event.depth,
            instructions=event.instructions,
            user_input=event.user_input,
            attachments=list(event.attachments),
        )
    if isinstance(event, runtime.StatusEvent):
        return ui.StatusEvent(
            worker=event.worker,
            depth=event.depth,
            phase=event.phase,
            state=event.state,
            model=event.model,
            duration_sec=event.duration_sec,
        )
    if isinstance(event, runtime.UserMessageEvent):
        return ui.UserMessageEvent(
            worker=event.worker,
            depth=event.depth,
            content=event.content,
        )
    if isinstance(event, runtime.TextResponseEvent):
        return ui.TextResponseEvent(
            worker=event.worker,
            depth=event.depth,
            content=event.content,
            is_complete=event.is_complete,
            is_delta=event.is_delta,
        )
    if isinstance(event, runtime.ToolCallEvent):
        return ui.ToolCallEvent(
            worker=event.worker,
            depth=event.depth,
            tool_name=event.tool_name,
            tool_call_id=event.tool_call_id,
            args=event.args,
            args_json=event.args_json,
        )
    if isinstance(event, runtime.ToolResultEvent):
        return ui.ToolResultEvent(
            worker=event.worker,
            depth=event.depth,
            tool_name=event.tool_name,
            tool_call_id=event.tool_call_id,
            content=event.content,
            is_error=event.is_error,
        )
    if isinstance(event, runtime.DeferredToolEvent):
        return ui.DeferredToolEvent(
            worker=event.worker,
            depth=event.depth,
            tool_name=event.tool_name,
            status=event.status,
        )
    if isinstance(event, runtime.CompletionEvent):
        return ui.CompletionEvent(worker=event.worker, depth=event.depth)
    if isinstance(event, runtime.ErrorEvent):
        return ui.ErrorEvent(
            worker=event.worker,
            depth=event.depth,
            message=event.message,
            error_type=event.error_type,
            traceback=event.traceback,
        )
    raise TypeError(f"Unsupported runtime event: {type(event)!r}")
