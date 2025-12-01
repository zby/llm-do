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
from pydantic_ai.builtin_tools import (
    CodeExecutionTool,
    ImageGenerationTool,
    UrlContextTool,
    WebSearchTool,
)
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models import Model as PydanticAIModel
from pydantic_ai.tools import RunContext

from pydantic_ai_filesystem_sandbox.approval import FileSandboxApprovalToolset
from .custom_toolset import CustomApprovalToolset
from .delegation_toolset import DelegationApprovalToolset
from .protocols import WorkerCreator, WorkerDelegator
from .shell_toolset import ShellApprovalToolset
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
        if config.tool_type == "web_search":
            tool = WebSearchTool(
                max_uses=config.max_uses,
                blocked_domains=config.blocked_domains,
                allowed_domains=config.allowed_domains,
            )
        elif config.tool_type == "url_context":
            tool = UrlContextTool()
        elif config.tool_type == "code_execution":
            tool = CodeExecutionTool()
        elif config.tool_type == "image_generation":
            tool = ImageGenerationTool()
        else:
            raise ValueError(f"Unknown server-side tool type: {config.tool_type}")
        tools.append(tool)
    return tools


def prepare_agent_execution(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
    *,
    delegator: Optional[WorkerDelegator] = None,
    creator: Optional[WorkerCreator] = None,
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
        delegator: Optional worker delegator for worker_call tool
        creator: Optional worker creator for worker_create tool

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

    # Build toolsets list
    toolsets = []

    # Sandbox toolset (provides read_file, write_file, edit_file, list_files)
    if context.sandbox is not None:
        approval_sandbox = FileSandboxApprovalToolset(
            inner=context.sandbox,
            approval_callback=context.approval_controller.approval_callback,
            memory=context.approval_controller.memory,
        )
        toolsets.append(approval_sandbox)

    # Shell toolset (provides shell command execution with pattern-based approval)
    if definition.shell_rules or definition.shell_default:
        shell_toolset = ShellApprovalToolset(
            rules=definition.shell_rules,
            default=definition.shell_default,
            cwd=context.shell_cwd,
            sandbox=context.sandbox,
            approval_callback=context.approval_controller.approval_callback,
            memory=context.approval_controller.memory,
        )
        toolsets.append(shell_toolset)

    # Delegation toolset (provides worker_call, worker_create with approval)
    if delegator is not None and creator is not None:
        delegation_toolset = DelegationApprovalToolset(
            delegator=delegator,
            creator=creator,
            allow_workers=definition.allow_workers,
            approval_callback=context.approval_controller.approval_callback,
            memory=context.approval_controller.memory,
        )
        toolsets.append(delegation_toolset)

    # Custom toolset (provides custom tools from tools.py with approval)
    if context.custom_tools_path and context.custom_tools_path.exists():
        allowed_tools = definition.custom_tools or []
        if allowed_tools:
            custom_toolset = CustomApprovalToolset(
                worker_name=definition.name,
                tools_path=context.custom_tools_path,
                allowed_tools=allowed_tools,
                approval_callback=context.approval_controller.approval_callback,
                memory=context.approval_controller.memory,
            )
            toolsets.append(custom_toolset)

    # Only pass toolsets if we have any
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
    delegator: Optional[WorkerDelegator] = None,
    creator: Optional[WorkerCreator] = None,
    register_tools_fn: Optional[Callable[[Agent, WorkerContext], None]] = None,
) -> tuple[Any, List[Any]]:
    """Async version of the default agent runner.

    This is the core async implementation that directly awaits agent.run().
    The sync version wraps this with asyncio.run().

    Args:
        definition: Worker definition with instructions and configuration
        user_input: Input data for the worker
        context: Worker execution context with tools and dependencies
        output_model: Optional Pydantic model for structured output
        delegator: Optional worker delegator for delegation toolset
        creator: Optional worker creator for delegation toolset
        register_tools_fn: Optional function to register additional tools

    Returns:
        Tuple of (output, messages) where messages is the list of all messages
        exchanged with the LLM during execution.
    """
    # Prepare execution context (prompt, callbacks, agent kwargs)
    exec_ctx = prepare_agent_execution(
        definition, user_input, context, output_model,
        delegator=delegator, creator=creator
    )

    # Create Agent
    agent = Agent(**exec_ctx.agent_kwargs)

    # Register any additional tools using injected function
    if register_tools_fn is not None:
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
    delegator: Optional[WorkerDelegator] = None,
    creator: Optional[WorkerCreator] = None,
    register_tools_fn: Optional[Callable[[Agent, WorkerContext], None]] = None,
) -> tuple[Any, List[Any]]:
    """Synchronous wrapper around the async agent runner.

    This provides backward compatibility for synchronous code that calls
    run_worker(). It simply wraps the async implementation with asyncio.run().

    Args:
        definition: Worker definition with instructions and configuration
        user_input: Input data for the worker
        context: Worker execution context with tools and dependencies
        output_model: Optional Pydantic model for structured output
        delegator: Optional worker delegator for delegation toolset
        creator: Optional worker creator for delegation toolset
        register_tools_fn: Optional function to register additional tools

    Returns:
        Tuple of (output, messages) where messages is the list of all messages
        exchanged with the LLM during execution.
    """
    # Simply wrap the async version with asyncio.run()
    return asyncio.run(
        default_agent_runner_async(
            definition, user_input, context, output_model,
            delegator=delegator,
            creator=creator,
            register_tools_fn=register_tools_fn
        )
    )
