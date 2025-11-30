"""Agent execution strategies for llm-do workers.

This module provides the default agent runners (sync and async)
and helper functions for preparing agent execution contexts.
"""
from __future__ import annotations

import asyncio
import json
import logging
from time import perf_counter
from typing import Any, Callable, Dict, List, Optional, Type, Union

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models import Model as PydanticAIModel
from pydantic_ai.tools import RunContext

from .tool_approval import ApprovalToolset
from .types import (
    AgentExecutionContext,
    ModelLike,
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


def format_user_prompt(user_input: Any) -> str:
    """Serialize user input into a prompt string for the agent.

    Args:
        user_input: Either a string or a JSON-serializable object

    Returns:
        String representation of the input
    """
    if isinstance(user_input, str):
        return user_input
    return json.dumps(user_input, indent=2, sort_keys=True)


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
    - Preparing agent kwargs
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
        context.message_callback(
            [{"worker": definition.name, "initial_request": preview}]
        )

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
            context.message_callback(
                [{"worker": definition.name, "status": status}]
            )

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

    # Conditionally include sandbox toolset if configured
    # Only pass toolsets parameter if we have a sandbox to avoid empty list issues
    if context.sandbox is not None:
        # Wrap sandbox with approval checking using unified controller
        approval_sandbox = ApprovalToolset(
            inner=context.sandbox,
            approval_callback=context.approval_controller.approval_callback,
            memory=context.approval_controller.memory,
        )
        agent_kwargs["toolsets"] = [approval_sandbox]  # Sandbox provides read_file, write_file, list_files

    if output_model is not None:
        agent_kwargs["output_type"] = output_model

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
    register_tools_fn: Callable[[Agent, WorkerContext], None],
) -> tuple[Any, List[Any]]:
    """Async version of the default agent runner.

    This is the core async implementation that directly awaits agent.run().
    The sync version wraps this with asyncio.run().

    Args:
        definition: Worker definition with instructions and configuration
        user_input: Input data for the worker
        context: Worker execution context with tools and dependencies
        output_model: Optional Pydantic model for structured output
        register_tools_fn: Function to register tools (injected via DI)

    Returns:
        Tuple of (output, messages) where messages is the list of all messages
        exchanged with the LLM during execution.
    """
    # Prepare execution context (prompt, callbacks, agent kwargs)
    exec_ctx = prepare_agent_execution(definition, user_input, context, output_model)

    # Create Agent
    agent = Agent(**exec_ctx.agent_kwargs)

    # Register tools using injected function
    register_tools_fn(agent, context)

    # Run the agent asynchronously
    run_result = await agent.run(
        exec_ctx.prompt,
        deps=context,
        event_stream_handler=exec_ctx.event_handler,
    )

    if exec_ctx.emit_status is not None and exec_ctx.started_at is not None:
        exec_ctx.emit_status("end", duration=round(perf_counter() - exec_ctx.started_at, 2))

    # Extract all messages from the result
    messages = run_result.all_messages() if hasattr(run_result, 'all_messages') else []

    return (run_result.output, messages)


def default_agent_runner(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
    *,
    register_tools_fn: Callable[[Agent, WorkerContext], None],
) -> tuple[Any, List[Any]]:
    """Synchronous wrapper around the async agent runner.

    This provides backward compatibility for synchronous code that calls
    run_worker(). It simply wraps the async implementation with asyncio.run().

    Args:
        definition: Worker definition with instructions and configuration
        user_input: Input data for the worker
        context: Worker execution context with tools and dependencies
        output_model: Optional Pydantic model for structured output
        register_tools_fn: Function to register tools (injected via DI)

    Returns:
        Tuple of (output, messages) where messages is the list of all messages
        exchanged with the LLM during execution.
    """
    # Simply wrap the async version with asyncio.run()
    return asyncio.run(
        default_agent_runner_async(
            definition, user_input, context, output_model,
            register_tools_fn=register_tools_fn
        )
    )
