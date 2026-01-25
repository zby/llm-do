"""Helpers for running PydanticAI agents inside the runtime."""
from __future__ import annotations

from collections.abc import AsyncIterable, Sequence
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserContent,
)
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset

from .args import get_display_text, normalize_input, render_prompt
from .contracts import AgentSpec, CallContextProtocol
from .event_parser import parse_event
from .events import ToolCallEvent, ToolResultEvent


def _get_all_messages(result: Any) -> list[Any]:
    """Return all messages from a run result or stream object."""
    return list(result.all_messages())


def _finalize_messages(
    agent_name: str,
    runtime: CallContextProtocol,
    result: Any,
    *,
    log_messages: bool = True,
) -> list[Any]:
    """Log and sync message history using a single message snapshot."""
    messages = _get_all_messages(result)
    if log_messages:
        runtime.log_messages(agent_name, runtime.frame.config.depth, messages)
    if runtime.frame.config.depth == 0:
        runtime.frame.messages[:] = messages
    return messages


class _MessageLogList(list):
    """List that logs new messages as they are appended."""

    def __init__(self, runtime: CallContextProtocol, agent_name: str, depth: int) -> None:
        super().__init__()
        self._runtime = runtime
        self._agent_name = agent_name
        self._depth = depth
        self._logged_count = 0

    def _log_new_messages(self, start: int) -> None:
        for message in list(self)[start:]:
            self._runtime.log_messages(self._agent_name, self._depth, [message])
        self._logged_count = len(self)

    def append(self, item: Any) -> None:  # type: ignore[override]
        super().append(item)
        self._log_new_messages(self._logged_count)

    def extend(self, items: list[Any]) -> None:  # type: ignore[override]
        start = len(self)
        super().extend(items)
        if len(self) > start:
            self._log_new_messages(start)


@contextmanager
def _capture_message_log(
    runtime: CallContextProtocol, *, agent_name: str, depth: int
) -> Any:
    """Capture and log messages as they are appended for this run."""
    from pydantic_ai._agent_graph import capture_run_messages, get_captured_run_messages

    with capture_run_messages():
        try:
            run_messages = get_captured_run_messages()
        except LookupError:
            yield
            return
        run_messages.messages = _MessageLogList(runtime, agent_name, depth)
        yield


def _build_agent(
    spec: AgentSpec,
    runtime: CallContextProtocol,
    *,
    toolsets: Sequence[AbstractToolset[Any]] | None = None,
) -> Agent[CallContextProtocol, Any]:
    """Build a PydanticAI agent with toolsets passed directly."""
    return Agent(
        model=spec.model,
        instructions=spec.instructions,
        output_type=spec.schema_out or str,
        deps_type=type(runtime),
        toolsets=list(toolsets) if toolsets else None,
        builtin_tools=spec.builtin_tools,
        end_strategy="exhaustive",
    )


def _emit_tool_events(
    agent_name: str, messages: list[Any], runtime: CallContextProtocol
) -> None:
    """Emit ToolCallEvent/ToolResultEvent for tool calls in messages."""
    # TODO: Consolidate tool-event fallback with streaming path (see docs/notes/reviews/tool-event-fallback-options.md).
    if runtime.config.on_event is None:
        return

    tool_calls: dict[str, ToolCallPart] = {}
    tool_returns: dict[str, ToolReturnPart] = {}

    for msg in messages:
        if isinstance(msg, ModelResponse):
            for response_part in msg.parts:
                if isinstance(response_part, ToolCallPart):
                    tool_calls[response_part.tool_call_id] = response_part
        elif isinstance(msg, ModelRequest):
            for request_part in msg.parts:
                if isinstance(request_part, ToolReturnPart):
                    tool_returns[request_part.tool_call_id] = request_part

    for call_id, call_part in tool_calls.items():
        runtime.config.on_event(
            ToolCallEvent(
                worker=agent_name,
                tool_name=call_part.tool_name,
                tool_call_id=call_id,
                args_json=call_part.args_as_json_str(),
                depth=runtime.frame.config.depth,
            )
        )

        return_part = tool_returns.get(call_id)
        if return_part:
            runtime.config.on_event(
                ToolResultEvent(
                    worker=agent_name,
                    depth=runtime.frame.config.depth,
                    tool_name=call_part.tool_name,
                    tool_call_id=call_id,
                    content=return_part.content,
                )
            )


async def _run_with_event_stream(
    spec: AgentSpec,
    agent: Agent[CallContextProtocol, Any],
    prompt: str | Sequence[UserContent],
    runtime: CallContextProtocol,
    message_history: list[Any] | None,
    *,
    log_messages: bool = True,
) -> tuple[Any, list[Any]]:
    """Run agent with event stream handler for UI updates."""
    from pydantic_ai.messages import PartDeltaEvent

    emitted_tool_events = False

    async def event_stream_handler(_: RunContext[CallContextProtocol], events: AsyncIterable[Any]) -> None:
        nonlocal emitted_tool_events
        async for event in events:
            if runtime.config.verbosity < 2 and isinstance(event, PartDeltaEvent):
                continue
            runtime_event = parse_event(
                {"worker": spec.name, "event": event, "depth": runtime.frame.config.depth}
            )
            if isinstance(runtime_event, (ToolCallEvent, ToolResultEvent)):
                emitted_tool_events = True
            if runtime.config.on_event is not None:
                runtime.config.on_event(runtime_event)

    result = await agent.run(
        prompt,
        deps=runtime,
        model_settings=spec.model_settings,
        event_stream_handler=event_stream_handler,
        message_history=message_history,
    )
    messages = _finalize_messages(spec.name, runtime, result, log_messages=log_messages)
    if runtime.config.on_event is not None and not emitted_tool_events:
        _emit_tool_events(spec.name, result.new_messages(), runtime)
    return result.output, messages


async def run_agent(
    spec: AgentSpec,
    runtime: CallContextProtocol,
    input_data: Any,
    *,
    message_history: list[Any] | None = None,
) -> tuple[Any, list[Any]]:
    """Run an agent for a single turn, returning output and messages."""
    _input_args, messages = normalize_input(spec.schema_in, input_data)
    runtime.frame.prompt = get_display_text(messages)

    agent = _build_agent(
        spec,
        runtime,
        toolsets=list(runtime.frame.config.active_toolsets),
    )
    base_path = runtime.config.project_root or Path.cwd()
    prompt = render_prompt(messages, base_path)

    use_incremental_log = runtime.config.message_log_callback is not None
    log_context = (
        _capture_message_log(
            runtime, agent_name=spec.name, depth=runtime.frame.config.depth
        )
        if use_incremental_log
        else nullcontext()
    )

    with log_context:
        if runtime.config.on_event is not None:
            output, run_messages = await _run_with_event_stream(
                spec,
                agent,
                prompt,
                runtime,
                message_history,
                log_messages=not use_incremental_log,
            )
        else:
            result = await agent.run(
                prompt,
                deps=runtime,
                model_settings=spec.model_settings,
                message_history=message_history,
            )
            run_messages = _finalize_messages(
                spec.name,
                runtime,
                result,
                log_messages=not use_incremental_log,
            )
            output = result.output

    return output, run_messages
