"""Agent execution strategies for llm-do workers.

This module provides the default async agent runner and helper functions
for preparing agent execution contexts.
"""
from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any, Callable, Dict, List, Optional, Type, Union

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.builtin_tools import (
    CodeExecutionTool,
    ImageGenerationTool,
    WebFetchTool,
    WebSearchTool,
)
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models import Model as PydanticAIModel
from pydantic_ai.tools import RunContext

from .toolset_loader import build_toolsets
from .oauth import resolve_oauth_overrides
from .types import (
    AgentExecutionContext,
    ModelLike,
    ServerSideToolConfig,
    WorkerContext,
    WorkerDefinition,
)

logger = logging.getLogger(__name__)


def model_supports_streaming(model: ModelLike) -> bool:
    """Return True if the configured model supports streaming callbacks.

    Args:
        model: Either a model string identifier or a PydanticAI Model instance

    Returns:
        True if the model supports streaming, False otherwise
    """
    if isinstance(model, str):
        # Assume vendor-provided identifiers support streaming
        return True

    # When the caller passes a Model subclass, only opt into streaming if the
    # subclass overrides request_stream. Comparing attribute identity avoids
    # invoking the method (which could raise NotImplementedError).
    base_stream = getattr(PydanticAIModel, "request_stream", None)
    model_stream = getattr(type(model), "request_stream", None)
    if base_stream is None or model_stream is None:
        return False
    return model_stream is not base_stream


def _json_default(obj: Any) -> Any:
    """Fallback serializer for json.dumps to handle common non-serializable types."""
    # Pydantic models
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    # Path-like objects
    if hasattr(obj, "__fspath__"):
        return str(obj)
    # datetime, date, time
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    # Fall back to string representation
    return str(obj)


def _merge_anthropic_beta_header(existing: Any, override: Any) -> Optional[str]:
    tokens: list[str] = []

    def _add_tokens(value: Any) -> None:
        if not value:
            return
        if isinstance(value, str):
            parts = value.split(",")
        elif isinstance(value, (list, tuple, set)):
            parts = list(value)
        else:
            parts = [str(value)]
        for part in parts:
            token = part.strip() if isinstance(part, str) else str(part).strip()
            if token and token not in tokens:
                tokens.append(token)

    _add_tokens(override)
    _add_tokens(existing)
    return ",".join(tokens) if tokens else None


def _merge_extra_headers(existing: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    for key, value in overrides.items():
        if key == "anthropic-beta":
            merged[key] = _merge_anthropic_beta_header(merged.get(key), value)
        else:
            merged[key] = value
    return merged


def _prepend_instructions(identity: str, instructions: Any) -> Any:
    if not instructions:
        return identity
    if isinstance(instructions, (list, tuple)):
        return [identity, *instructions]
    return [identity, instructions]


def format_user_prompt(user_input: Any) -> str:
    """Serialize user input into a prompt string for the agent.

    Args:
        user_input: Either a string or a JSON-serializable object

    Returns:
        String representation of the input
    """
    if isinstance(user_input, str):
        return user_input
    # Empty dict means no user input - use a default prompt
    if user_input == {}:
        return "Execute your task."
    return json.dumps(user_input, indent=2, sort_keys=True, default=_json_default)


# Registry of server-side tool factories
# Each factory takes a ServerSideToolConfig and returns a tool instance
SERVER_SIDE_TOOL_FACTORIES: Dict[str, Callable[[ServerSideToolConfig], Any]] = {
    "web_search": lambda cfg: WebSearchTool(
        max_uses=cfg.max_uses,
        blocked_domains=cfg.blocked_domains,
        allowed_domains=cfg.allowed_domains,
    ),
    "web_fetch": lambda cfg: WebFetchTool(),
    "code_execution": lambda cfg: CodeExecutionTool(),
    "image_generation": lambda cfg: ImageGenerationTool(),
}


def build_server_side_tools(
    configs: List[ServerSideToolConfig],
) -> List[Any]:
    """Convert server_side_tools config to pydantic-ai builtin_tools.

    Args:
        configs: List of ServerSideToolConfig from worker definition

    Returns:
        List of pydantic-ai builtin tool instances

    Raises:
        ValueError: If an unknown tool_type is specified
    """
    tools = []
    for config in configs:
        factory = SERVER_SIDE_TOOL_FACTORIES.get(config.tool_type)
        if factory is None:
            raise ValueError(
                f"Unknown server-side tool type: {config.tool_type}. "
                f"Available: {list(SERVER_SIDE_TOOL_FACTORIES.keys())}"
            )
        tools.append(factory(config))
    return tools


def prepare_agent_execution(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
) -> AgentExecutionContext:
    """Prepare everything needed for agent execution (sync or async).

    This extracts all the setup logic that's common between sync and async
    agent runners, including:
    - Building the prompt with attachments
    - Setting up streaming callbacks
    - Preparing agent kwargs with toolsets
    - Initializing status tracking

    Args:
        definition: Worker definition with instructions and configuration
        user_input: Input data for the worker
        context: Worker execution context with tools and dependencies
        output_model: Optional Pydantic model for structured output

    Returns:
        AgentExecutionContext with all prepared state for agent execution

    Raises:
        ValueError: If no model is configured for the worker
    """
    if context.effective_model is None:
        raise ValueError(
            f"No model configured for worker '{definition.name}'. "
            "Set worker.model, pass --model, or provide a custom agent_runner."
        )

    # Build user prompt with attachments
    prompt_text = format_user_prompt(user_input)
    attachment_labels = [item.display_name for item in context.attachments]

    if context.attachments:
        # Create a list of UserContent with text + file attachments
        user_content: List[Union[str, BinaryContent]] = [prompt_text]
        for attachment in context.attachments:
            binary_content = BinaryContent.from_path(attachment.path)
            user_content.append(binary_content)
        prompt = user_content
    else:
        # Just text, no attachments
        prompt = prompt_text

    # Setup callbacks and status tracking
    event_handler = None
    model_label: Optional[str] = None
    started_at: Optional[float] = None
    emit_status: Optional[Callable[[str, Optional[float]], None]] = None

    if context.message_callback:
        preview = {
            "instructions": definition.instructions or "",
            "user_input": prompt_text,
            "attachments": attachment_labels,
        }
        try:
            context.message_callback(
                [{"worker": definition.name, "initial_request": preview}]
            )
        except Exception as e:
            logger.exception("Error in initial_request callback: %s", e)

        def _emit_model_status(state: str, *, duration: Optional[float] = None) -> None:
            if not context.message_callback:
                return
            status: Dict[str, Any] = {
                "phase": "model_request",
                "state": state,
            }
            if model_label:
                status["model"] = model_label
            if duration is not None:
                status["duration_sec"] = duration
            try:
                context.message_callback(
                    [{"worker": definition.name, "status": status}]
                )
            except Exception as e:
                logger.exception("Error in status callback: %s", e)

        if model_supports_streaming(context.effective_model):
            # Note: The stream handler must be thread-safe since it will be called
            # from within the agent's event loop
            async def _stream_handler(
                run_ctx: RunContext[WorkerContext], event_stream
            ) -> None:  # pragma: no cover - exercised indirectly via integration tests
                async for event in event_stream:
                    # Call message_callback in a thread-safe way
                    try:
                        context.message_callback(
                            [{"worker": definition.name, "event": event}]
                        )
                    except Exception as e:
                        # Log but don't crash on callback errors
                        logger.exception("Error in stream handler callback: %s", e)

            event_handler = _stream_handler

        if isinstance(context.effective_model, str):
            model_label = context.effective_model
        elif context.effective_model is not None:
            model_label = (
                getattr(context.effective_model, "model_name", None)
                or context.effective_model.__class__.__name__
            )

        started_at = perf_counter()
        emit_status = _emit_model_status
        emit_status("start")

    # Prepare agent kwargs
    # PydanticAI expects the system prompt under the "instructions" parameter,
    # so even though WorkerDefinition refers to it as the worker's system
    # prompt, we keep passing it under that legacy keyword here.

    agent_kwargs: Dict[str, Any] = dict(
        model=context.effective_model,
        instructions=definition.instructions,
        name=definition.name,
        deps_type=WorkerContext,
    )

    # Build toolsets using the plugin loader
    if definition.toolsets:
        toolsets = build_toolsets(definition.toolsets, context)
        if toolsets:
            agent_kwargs["toolsets"] = toolsets

    if output_model is not None:
        agent_kwargs["output_type"] = output_model

    # Add server-side tools (provider-executed) if configured
    if definition.server_side_tools:
        agent_kwargs["builtin_tools"] = build_server_side_tools(definition.server_side_tools)

    return AgentExecutionContext(
        prompt=prompt,
        agent_kwargs=agent_kwargs,
        event_handler=event_handler,
        model_label=model_label,
        started_at=started_at,
        emit_status=emit_status,
    )


async def default_agent_runner_async(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
    *,
    register_tools_fn: Optional[Callable[[Agent, WorkerContext], None]] = None,
) -> tuple[Any, List[Any]]:
    """Async version of the default agent runner.

    This is the core async implementation that directly awaits agent.run().

    Args:
        definition: Worker definition with instructions and configuration
        user_input: Input data for the worker
        context: Worker execution context with tools and dependencies
        output_model: Optional Pydantic model for structured output
        register_tools_fn: Optional function to register additional tools

    Returns:
        Tuple of (output, messages) where messages is the list of all messages
        exchanged with the LLM during execution.
    """
    exec_ctx = prepare_agent_execution(
        definition, user_input, context, output_model
    )

    oauth_overrides = await resolve_oauth_overrides(context.effective_model)
    if oauth_overrides is not None:
        exec_ctx.agent_kwargs["model"] = oauth_overrides.model
        if oauth_overrides.model_settings:
            existing_settings = exec_ctx.agent_kwargs.get("model_settings")
            if isinstance(existing_settings, dict):
                merged = dict(existing_settings)
                extra_headers = _merge_extra_headers(
                    dict(merged.get("extra_headers", {})),
                    dict(oauth_overrides.model_settings.get("extra_headers", {})),
                )
                merged["extra_headers"] = extra_headers
                for key, value in oauth_overrides.model_settings.items():
                    if key != "extra_headers":
                        merged[key] = value
                exec_ctx.agent_kwargs["model_settings"] = merged
            else:
                exec_ctx.agent_kwargs["model_settings"] = oauth_overrides.model_settings
        if oauth_overrides.system_prompt:
            exec_ctx.agent_kwargs["instructions"] = _prepend_instructions(
                oauth_overrides.system_prompt,
                exec_ctx.agent_kwargs.get("instructions"),
            )

    # Create Agent
    agent = Agent(**exec_ctx.agent_kwargs)

    # Register any additional tools using injected function
    if register_tools_fn is not None:
        register_tools_fn(agent, context)

    # Run the agent asynchronously
    try:
        run_result = await agent.run(
            exec_ctx.prompt,
            deps=context,
            event_stream_handler=exec_ctx.event_handler,
        )
    except Exception:
        # Emit error status before re-raising
        if exec_ctx.emit_status is not None and exec_ctx.started_at is not None:
            exec_ctx.emit_status(
                "error", duration=round(perf_counter() - exec_ctx.started_at, 2)
            )
        raise
    else:
        if exec_ctx.emit_status is not None and exec_ctx.started_at is not None:
            exec_ctx.emit_status(
                "end", duration=round(perf_counter() - exec_ctx.started_at, 2)
            )

    # Extract all messages from the result
    # Handle both method and property forms for compatibility
    all_messages_attr = getattr(run_result, "all_messages", None)
    if callable(all_messages_attr):
        messages = all_messages_attr()
    elif all_messages_attr is not None:
        messages = all_messages_attr
    else:
        messages = []

    return (run_result.output, messages)
