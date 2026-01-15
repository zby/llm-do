"""Adapter to translate runtime events into UI events."""
from __future__ import annotations

from llm_do.runtime.events import (
    CompletionEvent as RuntimeCompletionEvent,
)
from llm_do.runtime.events import (
    DeferredToolEvent as RuntimeDeferredToolEvent,
)
from llm_do.runtime.events import (
    ErrorEvent as RuntimeErrorEvent,
)
from llm_do.runtime.events import (
    InitialRequestEvent as RuntimeInitialRequestEvent,
)
from llm_do.runtime.events import (
    RuntimeEvent,
)
from llm_do.runtime.events import (
    StatusEvent as RuntimeStatusEvent,
)
from llm_do.runtime.events import (
    TextResponseEvent as RuntimeTextResponseEvent,
)
from llm_do.runtime.events import (
    ToolCallEvent as RuntimeToolCallEvent,
)
from llm_do.runtime.events import (
    ToolResultEvent as RuntimeToolResultEvent,
)
from llm_do.runtime.events import (
    UserMessageEvent as RuntimeUserMessageEvent,
)

from .events import (
    CompletionEvent as UiCompletionEvent,
)
from .events import (
    DeferredToolEvent as UiDeferredToolEvent,
)
from .events import (
    ErrorEvent as UiErrorEvent,
)
from .events import (
    InitialRequestEvent as UiInitialRequestEvent,
)
from .events import (
    StatusEvent as UiStatusEvent,
)
from .events import (
    TextResponseEvent as UiTextResponseEvent,
)
from .events import (
    ToolCallEvent as UiToolCallEvent,
)
from .events import (
    ToolResultEvent as UiToolResultEvent,
)
from .events import (
    UIEvent,
)
from .events import (
    UserMessageEvent as UiUserMessageEvent,
)


def adapt_event(event: RuntimeEvent) -> UIEvent:
    """Convert a runtime event into its UI event equivalent."""
    if isinstance(event, RuntimeInitialRequestEvent):
        return UiInitialRequestEvent(
            worker=event.worker,
            depth=event.depth,
            instructions=event.instructions,
            user_input=event.user_input,
            attachments=list(event.attachments),
        )
    if isinstance(event, RuntimeStatusEvent):
        return UiStatusEvent(
            worker=event.worker,
            depth=event.depth,
            phase=event.phase,
            state=event.state,
            model=event.model,
            duration_sec=event.duration_sec,
        )
    if isinstance(event, RuntimeUserMessageEvent):
        return UiUserMessageEvent(
            worker=event.worker,
            depth=event.depth,
            content=event.content,
        )
    if isinstance(event, RuntimeTextResponseEvent):
        return UiTextResponseEvent(
            worker=event.worker,
            depth=event.depth,
            content=event.content,
            is_complete=event.is_complete,
            is_delta=event.is_delta,
        )
    if isinstance(event, RuntimeToolCallEvent):
        return UiToolCallEvent(
            worker=event.worker,
            depth=event.depth,
            tool_name=event.tool_name,
            tool_call_id=event.tool_call_id,
            args=event.args,
            args_json=event.args_json,
        )
    if isinstance(event, RuntimeToolResultEvent):
        return UiToolResultEvent(
            worker=event.worker,
            depth=event.depth,
            tool_name=event.tool_name,
            tool_call_id=event.tool_call_id,
            content=event.content,
            is_error=event.is_error,
        )
    if isinstance(event, RuntimeDeferredToolEvent):
        return UiDeferredToolEvent(
            worker=event.worker,
            depth=event.depth,
            tool_name=event.tool_name,
            status=event.status,
        )
    if isinstance(event, RuntimeCompletionEvent):
        return UiCompletionEvent(worker=event.worker, depth=event.depth)
    if isinstance(event, RuntimeErrorEvent):
        return UiErrorEvent(
            worker=event.worker,
            depth=event.depth,
            message=event.message,
            error_type=event.error_type,
            traceback=event.traceback,
        )
    raise TypeError(f"Unsupported runtime event: {type(event)!r}")
