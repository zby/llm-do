"""Helpers for running PydanticAI agents inside the runtime."""
from __future__ import annotations

from collections.abc import AsyncIterable, Sequence
from pathlib import Path
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.messages import UserContent
from pydantic_ai.settings import ModelSettings, merge_model_settings
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset

from ..oauth import get_oauth_provider_for_model_provider, resolve_oauth_overrides
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


def _split_model_identifier(model_id: str) -> tuple[str | None, str]:
    if ":" not in model_id:
        return None, model_id
    provider, name = model_id.split(":", 1)
    return provider, name


def _build_agent(
    spec: AgentSpec,
    runtime: CallContextProtocol,
    *,
    toolsets: Sequence[AbstractToolset[Any]] | None = None,
    model: Any | None = None,
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
    system_prompt: str | Sequence[str] | None = None

    auth_mode = runtime.config.auth_mode
    if auth_mode != "oauth_off":
        if spec.model_id is None:
            if auth_mode == "oauth_required":
                raise RuntimeError(
                    f"OAuth required for agent '{spec.name}', but model identifier is unavailable."
                )
        else:
            provider_name, _model_name = _split_model_identifier(spec.model_id)
            oauth_provider = get_oauth_provider_for_model_provider(provider_name or "")
            if oauth_provider is None:
                if auth_mode == "oauth_required":
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
                overrides = await resolve_oauth_overrides(spec.model_id)
                if overrides is None:
                    if auth_mode == "oauth_required":
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
                    system_prompt = overrides.system_prompt

    agent = _build_agent(
        spec,
        runtime,
        toolsets=list(runtime.frame.config.active_toolsets),
        model=model,
        system_prompt=system_prompt,
    )
    base_path = runtime.config.project_root or Path.cwd()
    prompt = render_prompt(messages, base_path)

    if runtime.config.on_event is not None:
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

    return output, run_messages
