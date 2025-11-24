"""Runtime orchestration for llm-do workers.

This module provides the core async runtime implementation:
- Agent execution (sync and async)
- Worker delegation and creation
- Tool registration and execution
- Approval and permission enforcement
- Context preparation and lifecycle management
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Type, Union

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models import Model as PydanticAIModel
from pydantic_ai.tools import RunContext

from .sandbox import SandboxManager, SandboxToolset
from .types import (
    AgentExecutionContext,
    AgentRunner,
    ApprovalCallback,
    ApprovalDecision,
    AttachmentInput,
    AttachmentPayload,
    MessageCallback,
    ModelLike,
    WorkerContext,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRunResult,
    WorkerSpec,
    approve_all_callback as _auto_approve_callback,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Approval controller
# ---------------------------------------------------------------------------


class ApprovalController:
    """Apply tool rules with blocking approval prompts."""

    def __init__(
        self,
        tool_rules: Mapping[str, Any],  # ToolRule from types
        *,
        approval_callback: ApprovalCallback = _auto_approve_callback,
    ):
        self.tool_rules = tool_rules
        self.approval_callback = approval_callback
        self.session_approvals: set[tuple[str, frozenset]] = set()

    def _make_approval_key(self, tool_name: str, payload: Mapping[str, Any]) -> tuple[str, frozenset]:
        """Create a hashable key for session approval tracking."""
        try:
            items = frozenset(payload.items())
        except TypeError:
            # If payload has unhashable values, use repr as fallback
            items = frozenset((k, repr(v)) for k, v in payload.items())
        return (tool_name, items)

    def maybe_run(
        self,
        tool_name: str,
        payload: Mapping[str, Any],
        func: Callable[[], Any],
    ) -> Any:
        rule = self.tool_rules.get(tool_name)
        if rule:
            if not rule.allowed:
                raise PermissionError(f"Tool '{tool_name}' is disallowed")
            if rule.approval_required:
                # Check session approvals
                key = self._make_approval_key(tool_name, payload)
                if key in self.session_approvals:
                    return func()

                # Block and wait for approval
                decision = self.approval_callback(tool_name, payload, rule.description)
                if not decision.approved:
                    note = f": {decision.note}" if decision.note else ""
                    raise PermissionError(f"User rejected tool call '{tool_name}'{note}")

                # Track session approval if requested
                if decision.approve_for_session:
                    self.session_approvals.add(key)

        return func()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _model_supports_streaming(model: ModelLike) -> bool:
    """Return True if the configured model supports streaming callbacks."""

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


def _format_user_prompt(user_input: Any) -> str:
    """Serialize user input into a prompt string for the agent."""

    if isinstance(user_input, str):
        return user_input
    return json.dumps(user_input, indent=2, sort_keys=True)


def _prepare_agent_execution(
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
    """
    if context.effective_model is None:
        raise ValueError(
            f"No model configured for worker '{definition.name}'. "
            "Set worker.model, pass --model, or provide a custom agent_runner."
        )

    # Build user prompt with attachments
    prompt_text = _format_user_prompt(user_input)
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

        if _model_supports_streaming(context.effective_model):
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
    agent_kwargs: Dict[str, Any] = dict(
        model=context.effective_model,
        instructions=definition.instructions,
        name=definition.name,
        deps_type=WorkerContext,
    )
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


# ---------------------------------------------------------------------------
# Tool registration and implementations
# ---------------------------------------------------------------------------


def _register_worker_tools(agent: Agent, context: WorkerContext) -> None:
    """Expose built-in llm-do helpers and custom tools as PydanticAI tools.

    Registers:
    1. Built-in tools (sandbox_*, worker_call, worker_create)
    2. Custom tools from tools.py if available
    """

    @agent.tool(name="sandbox_list", description="List files within a sandbox using a glob pattern")
    def sandbox_list(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        pattern: str = "**/*",
    ) -> List[str]:
        return ctx.deps.sandbox_toolset.list(sandbox, pattern)

    @agent.tool(name="sandbox_read_text", description="Read UTF-8 text from a sandboxed file. Do not use this on binary files (PDFs, images, etc) - pass them as attachments instead.")
    def sandbox_read_text(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        path: str,
        *,
        max_chars: int = 200_000,
    ) -> str:
        return ctx.deps.sandbox_toolset.read_text(sandbox, path, max_chars=max_chars)

    @agent.tool(name="sandbox_write_text", description="Write UTF-8 text to a sandboxed file")
    def sandbox_write_text(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        path: str,
        content: str,
    ) -> Optional[str]:
        return ctx.deps.sandbox_toolset.write_text(sandbox, path, content)

    @agent.tool(name="worker_call", description="Delegate to another registered worker")
    async def worker_call_tool(
        ctx: RunContext[WorkerContext],
        worker: str,
        input_data: Any = None,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        return await _worker_call_tool_async(
            ctx.deps,
            worker=worker,
            input_data=input_data,
            attachments=attachments,
        )

    @agent.tool(name="worker_create", description="Persist a new worker definition using the active profile")
    def worker_create_tool(
        ctx: RunContext[WorkerContext],
        name: str,
        instructions: str,
        description: Optional[str] = None,
        model: Optional[str] = None,
        output_schema_ref: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        return _worker_create_tool(
            ctx.deps,
            name=name,
            instructions=instructions,
            description=description,
            model=model,
            output_schema_ref=output_schema_ref,
            force=force,
        )

    # Load and register custom tools if available
    if context.custom_tools_path:
        _load_custom_tools(agent, context)


def _load_custom_tools(agent: Agent, context: WorkerContext) -> None:
    """Load and register custom tools from tools.py module.

    Custom tools are functions defined in the tools.py file in the worker's directory.
    Each function should have appropriate type hints and a docstring.

    The tools are registered with the agent and subject to the same approval
    rules as built-in tools via tool_rules in the worker definition.
    """
    import importlib.util
    import sys

    tools_path = context.custom_tools_path
    if not tools_path or not tools_path.exists():
        return

    # Load the module from the file path
    spec = importlib.util.spec_from_file_location(f"{context.worker.name}_tools", tools_path)
    if spec is None or spec.loader is None:
        logger.warning(f"Could not load custom tools from {tools_path}")
        return

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        logger.error(f"Error loading custom tools from {tools_path}: {e}")
        return

    # Register all callable functions from the module as tools
    # Functions with names starting with _ are considered private
    import inspect
    for name in dir(module):
        if name.startswith("_"):
            continue

        obj = getattr(module, name)
        if not (callable(obj) and inspect.isfunction(obj) and obj.__module__ == module.__name__):
            continue

        # Register using tool_plain since custom tools don't need WorkerContext
        try:
            # Use the function's existing signature and docstring
            agent.tool_plain(name=name, description=obj.__doc__ or f"Custom tool: {name}")(obj)
            logger.debug(f"Registered custom tool: {name}")
        except Exception as e:
            logger.warning(f"Could not register custom tool '{name}': {e}")


async def _worker_call_tool_async(
    ctx: WorkerContext,
    *,
    worker: str,
    input_data: Any = None,
    attachments: Optional[List[str]] = None,
) -> Any:
    """Async version of worker call tool - calls call_worker_async to avoid hangs."""
    resolved_attachments: List[Path]
    attachment_metadata: List[Dict[str, Any]]
    if attachments:
        resolved_attachments, attachment_metadata = ctx.validate_attachments(attachments)
    else:
        resolved_attachments, attachment_metadata = ([], [])

    attachment_payloads: Optional[List[AttachmentPayload]] = None
    if resolved_attachments:
        attachment_payloads = [
            AttachmentPayload(
                path=path,
                display_name=f"{meta['sandbox']}/{meta['path']}",
            )
            for path, meta in zip(resolved_attachments, attachment_metadata)
        ]

    async def _invoke() -> Any:
        result = await call_worker_async(
            registry=ctx.registry,
            worker=worker,
            input_data=input_data,
            caller_context=ctx,
            attachments=attachment_payloads,
        )
        return result.output

    payload: Dict[str, Any] = {"worker": worker}
    if attachment_metadata:
        payload["attachments"] = attachment_metadata

    # Check approval first (synchronously)
    rule = ctx.approval_controller.tool_rules.get("worker.call")
    if rule:
        if not rule.allowed:
            raise PermissionError(f"Tool 'worker.call' is disallowed")
        if rule.approval_required:
            # Check session approvals
            key = ctx.approval_controller._make_approval_key("worker.call", payload)
            if key not in ctx.approval_controller.session_approvals:
                # Block and wait for approval
                decision = ctx.approval_controller.approval_callback("worker.call", payload, rule.description)
                if not decision.approved:
                    note = f": {decision.note}" if decision.note else ""
                    raise PermissionError(f"User rejected tool call 'worker.call'{note}")
                # Track session approval if requested
                if decision.approve_for_session:
                    ctx.approval_controller.session_approvals.add(key)

    # Now execute async
    return await _invoke()


def _worker_call_tool(
    ctx: WorkerContext,
    *,
    worker: str,
    input_data: Any = None,
    attachments: Optional[List[str]] = None,
) -> Any:
    """Sync version of worker call tool - kept for backward compatibility."""
    resolved_attachments: List[Path]
    attachment_metadata: List[Dict[str, Any]]
    if attachments:
        resolved_attachments, attachment_metadata = ctx.validate_attachments(attachments)
    else:
        resolved_attachments, attachment_metadata = ([], [])

    attachment_payloads: Optional[List[AttachmentPayload]] = None
    if resolved_attachments:
        attachment_payloads = [
            AttachmentPayload(
                path=path,
                display_name=f"{meta['sandbox']}/{meta['path']}",
            )
            for path, meta in zip(resolved_attachments, attachment_metadata)
        ]

    def _invoke() -> Any:
        result = call_worker(
            registry=ctx.registry,
            worker=worker,
            input_data=input_data,
            caller_context=ctx,
            attachments=attachment_payloads,
        )
        return result.output

    payload: Dict[str, Any] = {"worker": worker}
    if attachment_metadata:
        payload["attachments"] = attachment_metadata

    return ctx.approval_controller.maybe_run(
        "worker.call",
        payload,
        _invoke,
    )


def _worker_create_tool(
    ctx: WorkerContext,
    *,
    name: str,
    instructions: str,
    description: Optional[str] = None,
    model: Optional[str] = None,
    output_schema_ref: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    spec = WorkerSpec(
        name=name,
        instructions=instructions,
        description=description,
        model=model,
        output_schema_ref=output_schema_ref,
    )

    def _invoke() -> Dict[str, Any]:
        created = create_worker(
            registry=ctx.registry,
            spec=spec,
            defaults=ctx.creation_defaults,
            force=force,
        )
        return created.model_dump(mode="json")

    return ctx.approval_controller.maybe_run(
        "worker.create",
        {"worker": name},
        _invoke,
    )


# ---------------------------------------------------------------------------
# Agent runners (sync and async)
# ---------------------------------------------------------------------------


async def _default_agent_runner_async(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
) -> tuple[Any, List[Any]]:
    """Async version of the default agent runner.

    This is the core async implementation that directly awaits agent.run().
    The sync version wraps this with asyncio.run().

    Args:
        definition: Worker definition with instructions and configuration
        user_input: Input data for the worker
        context: Worker execution context with tools and dependencies
        output_model: Optional Pydantic model for structured output

    Returns:
        Tuple of (output, messages) where messages is the list of all messages
        exchanged with the LLM during execution.
    """
    # Prepare execution context (prompt, callbacks, agent kwargs)
    exec_ctx = _prepare_agent_execution(definition, user_input, context, output_model)

    # Create Agent
    agent = Agent(**exec_ctx.agent_kwargs)
    _register_worker_tools(agent, context)

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


def _default_agent_runner(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
) -> tuple[Any, List[Any]]:
    """Synchronous wrapper around the async agent runner.

    This provides backward compatibility for synchronous code that calls
    run_worker(). It simply wraps the async implementation with asyncio.run().

    Args:
        definition: Worker definition with instructions and configuration
        user_input: Input data for the worker
        context: Worker execution context with tools and dependencies
        output_model: Optional Pydantic model for structured output

    Returns:
        Tuple of (output, messages) where messages is the list of all messages
        exchanged with the LLM during execution.
    """
    # Simply wrap the async version with asyncio.run()
    return asyncio.run(
        _default_agent_runner_async(definition, user_input, context, output_model)
    )


# ---------------------------------------------------------------------------
# Worker delegation
# ---------------------------------------------------------------------------


def call_worker(
    registry: Any,  # WorkerRegistry - avoid circular import
    worker: str,
    input_data: Any,
    *,
    caller_context: WorkerContext,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    agent_runner: AgentRunner = _default_agent_runner,
) -> WorkerRunResult:
    """Delegate to another worker (sync version)."""
    allowed = caller_context.worker.allow_workers
    if allowed:
        allowed_set = set(allowed)
        if "*" not in allowed_set and worker not in allowed_set:
            raise PermissionError(f"Delegation to '{worker}' is not allowed")
    return run_worker(
        registry=registry,
        worker=worker,
        input_data=input_data,
        caller_effective_model=caller_context.effective_model,
        attachments=attachments,
        creation_defaults=caller_context.creation_defaults,
        agent_runner=agent_runner,
        message_callback=caller_context.message_callback,
        approval_callback=caller_context.approval_controller.approval_callback,
    )


async def call_worker_async(
    registry: Any,  # WorkerRegistry - avoid circular import
    worker: str,
    input_data: Any,
    *,
    caller_context: WorkerContext,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    agent_runner: Optional[Callable] = None,
) -> WorkerRunResult:
    """Async version of call_worker for delegating to another worker.

    This is the key function that enables nested worker calls without hanging.
    By awaiting run_worker_async(), we stay within the same async context
    instead of creating conflicting event loops.

    Args:
        registry: Source for worker definitions.
        worker: Name of the worker to delegate to.
        input_data: Input payload for the delegated worker.
        caller_context: Context from the calling worker (for allowlist checks).
        attachments: Optional files to pass to the delegated worker.
        agent_runner: Optional async agent runner (defaults to async PydanticAI).

    Returns:
        WorkerRunResult from the delegated worker.
    """
    allowed = caller_context.worker.allow_workers
    if allowed:
        allowed_set = set(allowed)
        if "*" not in allowed_set and worker not in allowed_set:
            raise PermissionError(f"Delegation to '{worker}' is not allowed")
    return await run_worker_async(
        registry=registry,
        worker=worker,
        input_data=input_data,
        caller_effective_model=caller_context.effective_model,
        attachments=attachments,
        creation_defaults=caller_context.creation_defaults,
        agent_runner=agent_runner,
        message_callback=caller_context.message_callback,
        approval_callback=caller_context.approval_controller.approval_callback,
    )


# ---------------------------------------------------------------------------
# Worker creation
# ---------------------------------------------------------------------------


def create_worker(
    registry: Any,  # WorkerRegistry - avoid circular import
    spec: WorkerSpec,
    *,
    defaults: WorkerCreationDefaults,
    force: bool = False,
) -> WorkerDefinition:
    """Create and persist a new worker definition."""
    definition = defaults.expand_spec(spec)

    # Default to workers/generated/ for new workers
    path = registry.root / "workers" / "generated" / f"{spec.name}.yaml"

    registry.save_definition(definition, force=force, path=path)
    return definition


# ---------------------------------------------------------------------------
# Main worker execution (sync and async)
# ---------------------------------------------------------------------------


async def run_worker_async(
    *,
    registry: Any,  # WorkerRegistry - avoid circular import
    worker: str,
    input_data: Any,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    caller_effective_model: Optional[ModelLike] = None,
    cli_model: Optional[ModelLike] = None,
    creation_defaults: Optional[WorkerCreationDefaults] = None,
    agent_runner: Optional[Callable] = None,
    approval_callback: ApprovalCallback = _auto_approve_callback,
    message_callback: Optional[MessageCallback] = None,
) -> WorkerRunResult:
    """Execute a worker by name (async version).

    This is the async entry point for running workers. It handles:
    1. Loading the worker definition.
    2. Setting up the runtime environment (sandboxes, tools, approvals).
    3. Creating the execution context.
    4. Awaiting the async agent runner.

    Args:
        registry: Source for worker definitions.
        worker: Name of the worker to run.
        input_data: Input payload for the worker.
        attachments: Optional files to expose to the worker.
        caller_effective_model: Inherited model from parent (used if worker has no model).
        cli_model: Fallback model from CLI (used if neither worker nor parent has a model).
        creation_defaults: Defaults for any new workers created during this run.
        agent_runner: Optional async strategy for executing the agent (defaults to async PydanticAI).
        approval_callback: Callback for tool approval requests.
        message_callback: Callback for streaming events and progress updates.

    Returns:
        WorkerRunResult containing the final output and message history.
    """
    definition = registry.load_definition(worker)
    custom_tools_path = registry.find_custom_tools(worker)

    defaults = creation_defaults or WorkerCreationDefaults()
    sandbox_manager = SandboxManager(definition.sandboxes or defaults.default_sandboxes)

    attachment_policy = definition.attachment_policy

    attachment_payloads: List[AttachmentPayload] = []
    if attachments:
        for item in attachments:
            if isinstance(item, AttachmentPayload):
                attachment_payloads.append(item)
                continue

            display_name = str(item)
            path = Path(item).expanduser().resolve()
            attachment_payloads.append(
                AttachmentPayload(path=path, display_name=display_name)
            )

    attachment_policy.validate_paths([payload.path for payload in attachment_payloads])

    effective_model = definition.model or caller_effective_model or cli_model

    approvals = ApprovalController(definition.tool_rules, approval_callback=approval_callback)
    sandbox_tools = SandboxToolset(sandbox_manager, approvals)

    context = WorkerContext(
        registry=registry,
        worker=definition,
        sandbox_manager=sandbox_manager,
        sandbox_toolset=sandbox_tools,
        creation_defaults=defaults,
        effective_model=effective_model,
        attachments=attachment_payloads,
        approval_controller=approvals,
        message_callback=message_callback,
        custom_tools_path=custom_tools_path,
    )

    output_model = registry.resolve_output_schema(definition)

    # Use the provided agent_runner or default to the async version
    if agent_runner is None:
        result = await _default_agent_runner_async(definition, input_data, context, output_model)
    else:
        # Support both sync and async agent runners
        if inspect.iscoroutinefunction(agent_runner):
            result = await agent_runner(definition, input_data, context, output_model)
        else:
            result = agent_runner(definition, input_data, context, output_model)

    # Handle both old-style (output only) and new-style (output, messages) returns
    if isinstance(result, tuple) and len(result) == 2:
        raw_output, messages = result
    else:
        raw_output = result
        messages = []

    if output_model is not None:
        output = output_model.model_validate(raw_output)
    else:
        output = raw_output

    return WorkerRunResult(output=output, messages=messages)


def run_worker(
    *,
    registry: Any,  # WorkerRegistry - avoid circular import
    worker: str,
    input_data: Any,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    caller_effective_model: Optional[ModelLike] = None,
    cli_model: Optional[ModelLike] = None,
    creation_defaults: Optional[WorkerCreationDefaults] = None,
    agent_runner: AgentRunner = _default_agent_runner,
    approval_callback: ApprovalCallback = _auto_approve_callback,
    message_callback: Optional[MessageCallback] = None,
) -> WorkerRunResult:
    """Execute a worker by name.

    This is the primary entry point for running workers. It handles:
    1. Loading the worker definition.
    2. Setting up the runtime environment (sandboxes, tools, approvals).
    3. Creating the execution context.
    4. Delegating the actual agent loop to the provided ``agent_runner``.

    Args:
        registry: Source for worker definitions.
        worker: Name of the worker to run.
        input_data: Input payload for the worker.
        attachments: Optional files to expose to the worker.
        caller_effective_model: Inherited model from parent (used if worker has no model).
        cli_model: Fallback model from CLI (used if neither worker nor parent has a model).
        creation_defaults: Defaults for any new workers created during this run.
        agent_runner: Strategy for executing the agent (defaults to PydanticAI).
        approval_callback: Callback for tool approval requests.
        message_callback: Callback for streaming events and progress updates.

    Returns:
        WorkerRunResult containing the final output and message history.
    """
    definition = registry.load_definition(worker)
    custom_tools_path = registry.find_custom_tools(worker)

    defaults = creation_defaults or WorkerCreationDefaults()
    sandbox_manager = SandboxManager(definition.sandboxes or defaults.default_sandboxes)

    attachment_policy = definition.attachment_policy

    attachment_payloads: List[AttachmentPayload] = []
    if attachments:
        for item in attachments:
            if isinstance(item, AttachmentPayload):
                attachment_payloads.append(item)
                continue

            display_name = str(item)
            path = Path(item).expanduser().resolve()
            attachment_payloads.append(
                AttachmentPayload(path=path, display_name=display_name)
            )

    attachment_policy.validate_paths([payload.path for payload in attachment_payloads])

    effective_model = definition.model or caller_effective_model or cli_model

    approvals = ApprovalController(definition.tool_rules, approval_callback=approval_callback)
    sandbox_tools = SandboxToolset(sandbox_manager, approvals)

    context = WorkerContext(
        registry=registry,
        worker=definition,
        sandbox_manager=sandbox_manager,
        sandbox_toolset=sandbox_tools,
        creation_defaults=defaults,
        effective_model=effective_model,
        attachments=attachment_payloads,
        approval_controller=approvals,
        message_callback=message_callback,
        custom_tools_path=custom_tools_path,
    )

    output_model = registry.resolve_output_schema(definition)

    # Real agent integration would expose toolsets to the model here. The base
    # implementation simply forwards to the agent runner with the constructed
    # context.
    result = agent_runner(definition, input_data, context, output_model)

    # Handle both old-style (output only) and new-style (output, messages) returns
    if isinstance(result, tuple) and len(result) == 2:
        raw_output, messages = result
    else:
        raw_output = result
        messages = []

    if output_model is not None:
        output = output_model.model_validate(raw_output)
    else:
        output = raw_output

    return WorkerRunResult(output=output, messages=messages)
