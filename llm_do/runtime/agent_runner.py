"""Helpers for running PydanticAI agents inside the runtime."""
from __future__ import annotations

from collections.abc import AsyncIterable, Sequence
from pathlib import Path
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.messages import (
    BuiltinToolCallEvent,
    BuiltinToolCallPart,
    BuiltinToolResultEvent,
    BuiltinToolReturnPart,
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelRequest,
    ModelResponse,
    PartEndEvent,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserContent,
)
from pydantic_ai.settings import ModelSettings, merge_model_settings
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset

from .args import get_display_text, normalize_input, render_prompt
from .contracts import AgentSpec, CallContextProtocol
from .events import RuntimeEvent


def _get_all_messages(result: Any) -> list[Any]:
    """Return all messages from a run result or stream object."""
    return list(result.all_messages())


def _finalize_messages(
    agent_name: str,
    runtime: CallContextProtocol,
    result: Any,
) -> list[Any]:
    """Log and sync message history using a single message snapshot."""
    messages = _get_all_messages(result)
    runtime.log_messages(agent_name, runtime.frame.config.depth, messages)
    if runtime.frame.config.depth == 0:
        runtime.frame.messages[:] = messages
    return messages


def _emit_runtime_event(
    spec: AgentSpec,
    runtime: CallContextProtocol,
    event: Any,
) -> None:
    on_event = runtime.config.on_event
    if on_event is None:
        return
    on_event(
        RuntimeEvent(
            agent=spec.name,
            depth=runtime.frame.config.depth,
            event=event,
        )
    )


def _emit_non_stream_events(
    spec: AgentSpec,
    runtime: CallContextProtocol,
    run_messages: list[Any],
) -> None:
    """Emit coarse-grained events from final messages when streaming is disabled."""
    for message in run_messages:
        if isinstance(message, ModelResponse):
            for i, response_part in enumerate(message.parts):
                if isinstance(response_part, ToolCallPart):
                    _emit_runtime_event(spec, runtime, FunctionToolCallEvent(part=response_part))
                    continue
                if isinstance(response_part, BuiltinToolCallPart):
                    _emit_runtime_event(spec, runtime, BuiltinToolCallEvent(part=response_part))
                    continue
                if isinstance(response_part, TextPart):
                    next_part_kind = message.parts[i + 1].part_kind if i + 1 < len(message.parts) else None
                    _emit_runtime_event(
                        spec,
                        runtime,
                        PartEndEvent(index=i, part=response_part, next_part_kind=next_part_kind),
                    )
        elif isinstance(message, ModelRequest):
            for request_part in message.parts:
                if isinstance(request_part, (ToolReturnPart, RetryPromptPart)) and getattr(request_part, "tool_name", None):
                    _emit_runtime_event(spec, runtime, FunctionToolResultEvent(result=request_part))
                    continue
                if isinstance(request_part, BuiltinToolReturnPart):
                    _emit_runtime_event(spec, runtime, BuiltinToolResultEvent(result=request_part))

    _emit_runtime_event(spec, runtime, FinalResultEvent(tool_name=None, tool_call_id=None))


def _split_model_identifier(model_id: str) -> tuple[str | None, str]:
    if ":" not in model_id:
        return None, model_id
    provider, name = model_id.split(":", 1)
    return provider, name


def _resolve_oauth_provider_for_model_provider(
    runtime: CallContextProtocol,
    model_provider: str,
) -> str | None:
    provider_resolver = runtime.config.oauth_provider_resolver
    if provider_resolver is None:
        return None
    return provider_resolver(model_provider)


async def _resolve_oauth_model_overrides(
    runtime: CallContextProtocol,
    model_id: str,
) -> Any | None:
    override_resolver = runtime.config.oauth_override_resolver
    if override_resolver is None:
        return None
    return await override_resolver(model_id)


def _build_agent(
    spec: AgentSpec,
    runtime: CallContextProtocol,
    *,
    tools: Sequence[Any] | None = None,
    toolsets: Sequence[AbstractToolset[Any]] | None = None,
    model: Any | None = None,
    # system_prompt is intentionally kept for future use (e.g., per-call prompt
    # injection). Not currently wired from run_agent but part of PydanticAI's API.
    system_prompt: str | Sequence[str] | None = None,
) -> Agent[CallContextProtocol, Any]:
    """Build a PydanticAI agent with toolsets passed directly."""
    selected_model = model or spec.model
    system_prompt_value: str | Sequence[str] = system_prompt or ()
    return Agent(
        model=selected_model,
        instructions=spec.instructions,
        system_prompt=system_prompt_value,
        output_type=spec.output_model or str,
        deps_type=type(runtime),
        tools=list(tools) if tools else (),
        toolsets=list(toolsets) if toolsets else None,
        builtin_tools=spec.builtin_tools,
        end_strategy="exhaustive",
    )


async def _run_with_event_stream(
    spec: AgentSpec,
    agent: Agent[CallContextProtocol, Any],
    prompt: str | Sequence[UserContent],
    runtime: CallContextProtocol,
    message_history: list[Any] | None,
    model_settings: ModelSettings | None,
) -> tuple[Any, list[Any]]:
    """Run agent with event stream handler for UI updates."""
    on_event = runtime.config.on_event
    assert on_event is not None

    async def event_stream_handler(_: RunContext[CallContextProtocol], events: AsyncIterable[Any]) -> None:
        async for event in events:
            on_event(
                RuntimeEvent(
                    agent=spec.name,
                    depth=runtime.frame.config.depth,
                    event=event,
                )
            )

    result = await agent.run(
        prompt,
        deps=runtime,
        model_settings=model_settings,
        event_stream_handler=event_stream_handler,
        message_history=message_history,
    )
    messages = _finalize_messages(spec.name, runtime, result)
    return result.output, messages


async def run_agent(
    spec: AgentSpec,
    runtime: CallContextProtocol,
    input_data: Any,
    *,
    message_history: list[Any] | None = None,
) -> tuple[Any, list[Any]]:
    """Run an agent for a single turn, returning output and messages."""
    _input_args, messages = normalize_input(spec.input_model, input_data)
    runtime.frame.prompt = get_display_text(messages)

    model = spec.model
    model_settings = spec.model_settings

    auth_mode = runtime.config.auth_mode
    if auth_mode != "oauth_off":
        if spec.model_id is None:
            if auth_mode == "oauth_required":
                raise RuntimeError(
                    f"OAuth required for agent '{spec.name}', but model identifier is unavailable."
                )
        else:
            provider_name, _model_name = _split_model_identifier(spec.model_id)
            oauth_provider = _resolve_oauth_provider_for_model_provider(
                runtime,
                provider_name or "",
            )
            if oauth_provider is None:
                if auth_mode == "oauth_required":
                    if runtime.config.oauth_provider_resolver is None:
                        raise RuntimeError(
                            f"OAuth required for agent '{spec.name}', "
                            "but OAuth provider resolver is not configured."
                        )
                    if provider_name:
                        raise RuntimeError(
                            f"OAuth required for agent '{spec.name}', "
                            f"but provider '{provider_name}' does not support OAuth."
                        )
                    raise RuntimeError(
                        f"OAuth required for agent '{spec.name}', "
                        f"but model '{spec.model_id}' has no provider prefix."
                    )
            else:
                overrides = await _resolve_oauth_model_overrides(runtime, spec.model_id)
                if overrides is None:
                    if auth_mode == "oauth_required":
                        if runtime.config.oauth_override_resolver is None:
                            raise RuntimeError(
                                f"OAuth required for agent '{spec.name}', "
                                "but OAuth override resolver is not configured."
                            )
                        raise RuntimeError(
                            f"OAuth required for agent '{spec.name}', "
                            f"but no OAuth credentials found for '{oauth_provider}'."
                        )
                else:
                    model = overrides.model
                    model_settings = merge_model_settings(
                        model_settings,
                        overrides.model_settings,
                    )

    agent = _build_agent(
        spec,
        runtime,
        tools=spec.tools,
        toolsets=list(runtime.frame.config.active_toolsets),
        model=model,
    )
    base_path = runtime.config.project_root or Path.cwd()
    prompt = render_prompt(messages, base_path)

    async with agent:
        use_streaming_events = runtime.config.on_event is not None and runtime.config.verbosity >= 2
        if use_streaming_events:
            output, run_messages = await _run_with_event_stream(
                spec,
                agent,
                prompt,
                runtime,
                message_history,
                model_settings,
            )
        else:
            result = await agent.run(
                prompt,
                deps=runtime,
                model_settings=model_settings,
                message_history=message_history,
            )
            run_messages = _finalize_messages(
                spec.name,
                runtime,
                result,
            )
            output = result.output
            if runtime.config.on_event is not None:
                _emit_non_stream_events(spec, runtime, run_messages)

    return output, run_messages
