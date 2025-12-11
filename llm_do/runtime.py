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
from pydantic_ai.tools import (
    DeferredToolRequests,
    DeferredToolResults,
    RunContext,
    ToolApproved,
)
from pydantic_ai import ToolDenied

from .execution import default_agent_runner_async, default_agent_runner, prepare_agent_execution
from .model_compat import select_model, ModelCompatibilityError, NoModelError
from pydantic_ai_blocking_approval import (
    ApprovalController,
    ApprovalDecision,
)
from .sandbox import AttachmentInput, AttachmentPayload
from .worker_sandbox import AttachmentValidator, Sandbox, SandboxConfig
# Tools are now provided via toolsets in execution.py
from .types import (
    AgentExecutionContext,
    AgentRunner,
    MessageCallback,
    ModelLike,
    WorkerContext,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRunResult,
    WorkerSpec,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Type aliases for deferred tool handling
# ---------------------------------------------------------------------------

# Callback type for handling deferred tool approval requests
# Takes DeferredToolRequests, returns DeferredToolResults with approval decisions
DeferredApprovalHandler = Callable[
    [DeferredToolRequests],
    "asyncio.coroutines.Coroutine[Any, Any, DeferredToolResults]"
]

# Callback type for handling external/background tool calls
# Takes DeferredToolRequests, returns DeferredToolResults with computed results
DeferredCallHandler = Callable[
    [DeferredToolRequests],
    "asyncio.coroutines.Coroutine[Any, Any, DeferredToolResults]"
]


# ---------------------------------------------------------------------------
# Helper dataclasses
# ---------------------------------------------------------------------------


@dataclass
class _WorkerExecutionPrep:
    """Prepared context and metadata for worker execution."""
    context: WorkerContext
    definition: WorkerDefinition
    output_model: Optional[Type[BaseModel]]
    sandbox: Optional[Sandbox]


def _prepare_worker_context(
    *,
    registry: Any,
    worker: str,
    input_data: Any,
    attachments: Optional[Sequence[AttachmentInput]],
    caller_effective_model: Optional[ModelLike],
    cli_model: Optional[ModelLike],
    creation_defaults: Optional[WorkerCreationDefaults],
    approval_controller: ApprovalController,
    message_callback: Optional[MessageCallback],
) -> _WorkerExecutionPrep:
    """Prepare worker context and dependencies (shared by sync and async).

    This extracts all the common setup logic that's identical between
    run_worker and run_worker_async, reducing ~110 lines of duplication.
    """
    definition = registry.load_definition(worker)
    custom_tools_path = registry.find_custom_tools(worker)

    defaults = creation_defaults or WorkerCreationDefaults()

    # Create sandbox only if configured
    new_sandbox: Optional[Sandbox] = None
    attachment_validator: Optional[AttachmentValidator] = None

    sandbox_config = definition.sandbox
    default_sandbox_config = defaults.default_sandbox

    if sandbox_config is not None:
        # Worker has explicit sandbox config
        new_sandbox = Sandbox(sandbox_config, base_path=registry.root)
        attachment_validator = AttachmentValidator(new_sandbox)
        logger.debug(f"Using unified sandbox for worker '{worker}'")
    elif default_sandbox_config is not None:
        # Use default sandbox from creation defaults
        new_sandbox = Sandbox(default_sandbox_config, base_path=registry.root)
        attachment_validator = AttachmentValidator(new_sandbox)
        logger.debug(f"Using default sandbox for worker '{worker}'")
    else:
        # No sandbox - worker doesn't use file I/O
        logger.debug(f"Worker '{worker}' has no sandbox - file tools disabled")

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

    # Validate attachments against receiver's policy (type/count/size constraints)
    # Note: Sandbox validation (can caller access?) happens at caller side
    if attachment_payloads:
        definition.attachment_policy.validate_paths([payload.path for payload in attachment_payloads])

    # Select model with compatibility validation
    # Resolution: worker.model > cli_model > caller_model, validated against compatible_models
    # ModelCompatibilityError propagates immediately (user error)
    # NoModelError is deferred to execution (backward compat with custom agent_runners)
    effective_model: Optional[ModelLike] = None
    try:
        effective_model = select_model(
            worker_model=definition.model,
            cli_model=cli_model,
            caller_model=caller_effective_model,
            compatible_models=definition.compatible_models,
            worker_name=worker,
        )
    except NoModelError:
        # No model available - will be caught later in execution
        # This keeps backward compatibility with workers that use custom agent_runner
        pass
    # ModelCompatibilityError propagates - user needs to fix the incompatible model

    context = WorkerContext(
        # Core
        worker=definition,
        effective_model=effective_model,
        approval_controller=approval_controller,
        # Delegation
        registry=registry,
        creation_defaults=defaults,
        attachment_validator=attachment_validator,
        # I/O
        sandbox=new_sandbox,
        attachments=attachment_payloads,
        # Callbacks
        message_callback=message_callback,
        custom_tools_path=custom_tools_path,
    )

    output_model = registry.resolve_output_schema(definition)

    return _WorkerExecutionPrep(
        context=context,
        definition=definition,
        output_model=output_model,
        sandbox=new_sandbox,
    )


def _handle_result(
    result: Any,
    output_model: Optional[Type[BaseModel]],
) -> WorkerRunResult:
    """Handle agent result and convert to WorkerRunResult (shared by sync and async)."""
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


# ---------------------------------------------------------------------------
# Worker delegation
# ---------------------------------------------------------------------------


def _check_delegation_allowed(caller_context: WorkerContext, worker: str) -> None:
    """Check if delegation to a worker is allowed (shared by sync and async)."""
    toolsets = caller_context.worker.toolsets or {}
    delegation_config = toolsets.get("delegation", {})
    allowed = delegation_config.get("allow_workers", [])
    if allowed:
        allowed_set = set(allowed)
        if "*" not in allowed_set and worker not in allowed_set:
            raise PermissionError(f"Delegation to '{worker}' is not allowed")


def call_worker(
    registry: Any,  # WorkerRegistry - avoid circular import
    worker: str,
    input_data: Any,
    *,
    caller_context: WorkerContext,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    agent_runner: Optional[AgentRunner] = None,
) -> WorkerRunResult:
    """Delegate to another worker (sync version)."""
    _check_delegation_allowed(caller_context, worker)
    return run_worker(
        registry=registry,
        worker=worker,
        input_data=input_data,
        caller_effective_model=caller_context.effective_model,
        attachments=attachments,
        creation_defaults=caller_context.creation_defaults,
        agent_runner=agent_runner,
        message_callback=caller_context.message_callback,
        approval_controller=caller_context.approval_controller,
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
    _check_delegation_allowed(caller_context, worker)
    return await run_worker_async(
        registry=registry,
        worker=worker,
        input_data=input_data,
        caller_effective_model=caller_context.effective_model,
        attachments=attachments,
        creation_defaults=caller_context.creation_defaults,
        agent_runner=agent_runner,
        message_callback=caller_context.message_callback,
        approval_controller=caller_context.approval_controller,
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
    """Create and persist a new worker definition.

    Generated workers are saved to /tmp/llm-do/generated/ and registered
    with the registry so they can be found in this session.

    Raises:
        FileExistsError: If a worker with this name already exists anywhere
            (project, built-in, or generated dir) and force=False.
    """
    # Check for conflicts - never overwrite without force
    if not force and registry.worker_exists(spec.name):
        raise FileExistsError(
            f"Worker '{spec.name}' already exists. Use a different name or remove the existing worker."
        )

    definition = defaults.expand_spec(spec)

    # Generated workers are directories: {generated_dir}/{name}/worker.worker
    worker_dir = registry.generated_dir / spec.name
    path = worker_dir / "worker.worker"

    registry.save_definition(definition, force=force, path=path)
    registry.register_generated(spec.name)
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
    approval_controller: Optional[ApprovalController] = None,
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
        approval_controller: Controller for tool approval (defaults to approve-all mode).
        message_callback: Callback for streaming events and progress updates.

    Returns:
        WorkerRunResult containing the final output and message history.
    """
    if approval_controller is None:
        approval_controller = ApprovalController(mode="approve_all")

    prep = _prepare_worker_context(
        registry=registry,
        worker=worker,
        input_data=input_data,
        attachments=attachments,
        caller_effective_model=caller_effective_model,
        cli_model=cli_model,
        creation_defaults=creation_defaults,
        approval_controller=approval_controller,
        message_callback=message_callback,
    )

    # Use the provided agent_runner or default to the async version
    # Delegator/creator are now accessed via prep.context.delegator/.creator
    if agent_runner is None:
        result = await default_agent_runner_async(
            prep.definition, input_data, prep.context, prep.output_model
        )
    else:
        # Support both sync and async agent runners
        if inspect.iscoroutinefunction(agent_runner):
            result = await agent_runner(prep.definition, input_data, prep.context, prep.output_model)
        else:
            result = agent_runner(prep.definition, input_data, prep.context, prep.output_model)

    return _handle_result(result, prep.output_model)


def run_worker(
    *,
    registry: Any,  # WorkerRegistry - avoid circular import
    worker: str,
    input_data: Any,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    caller_effective_model: Optional[ModelLike] = None,
    cli_model: Optional[ModelLike] = None,
    creation_defaults: Optional[WorkerCreationDefaults] = None,
    agent_runner: Optional[AgentRunner] = None,
    approval_controller: Optional[ApprovalController] = None,
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
        approval_controller: Controller for tool approval (defaults to approve-all mode).
        message_callback: Callback for streaming events and progress updates.

    Returns:
        WorkerRunResult containing the final output and message history.
    """
    if approval_controller is None:
        approval_controller = ApprovalController(mode="approve_all")

    prep = _prepare_worker_context(
        registry=registry,
        worker=worker,
        input_data=input_data,
        attachments=attachments,
        caller_effective_model=caller_effective_model,
        cli_model=cli_model,
        creation_defaults=creation_defaults,
        approval_controller=approval_controller,
        message_callback=message_callback,
    )

    # Real agent integration would expose toolsets to the model here. The base
    # implementation simply forwards to the agent runner with the constructed
    # context. Delegator/creator are accessed via prep.context.
    if agent_runner is None:
        result = default_agent_runner(
            prep.definition, input_data, prep.context, prep.output_model
        )
    else:
        result = agent_runner(prep.definition, input_data, prep.context, prep.output_model)

    return _handle_result(result, prep.output_model)


# ---------------------------------------------------------------------------
# Deferred tool execution (native pydantic-ai pattern)
# ---------------------------------------------------------------------------


async def run_worker_with_deferred_async(
    *,
    registry: Any,  # WorkerRegistry - avoid circular import
    worker: str,
    input_data: Any,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    caller_effective_model: Optional[ModelLike] = None,
    cli_model: Optional[ModelLike] = None,
    creation_defaults: Optional[WorkerCreationDefaults] = None,
    approval_handler: Optional[DeferredApprovalHandler] = None,
    call_handler: Optional[DeferredCallHandler] = None,
    message_callback: Optional[MessageCallback] = None,
    max_iterations: int = 100,
) -> WorkerRunResult:
    """Execute a worker with native pydantic-ai deferred tool support.

    This is an alternative to run_worker_async that uses pydantic-ai's native
    deferred tool mechanism instead of blocking approvals. When a tool raises
    ApprovalRequired or CallDeferred, execution pauses and the appropriate
    handler is called to get the results, then execution resumes.

    This enables:
    - Non-blocking approval prompts
    - Background task processing
    - State persistence for pause/resume workflows
    - Concurrent I/O during approval waiting

    Args:
        registry: Source for worker definitions.
        worker: Name of the worker to run.
        input_data: Input payload for the worker.
        attachments: Optional files to expose to the worker.
        caller_effective_model: Inherited model from parent.
        cli_model: Fallback model from CLI.
        creation_defaults: Defaults for any new workers created during this run.
        approval_handler: Async callback to handle approval requests.
            Called with DeferredToolRequests when tools need approval.
            Should return DeferredToolResults with approval decisions.
        call_handler: Async callback to handle external/background tool calls.
            Called with DeferredToolRequests when tools are deferred.
            Should return DeferredToolResults with computed results.
        message_callback: Callback for streaming events and progress updates.
        max_iterations: Maximum deferred tool loop iterations (safety limit).

    Returns:
        WorkerRunResult containing the final output and message history.

    Raises:
        RuntimeError: If max_iterations is exceeded (likely infinite loop).
    """
    from .execution import prepare_agent_execution
    from .toolset_loader import build_toolsets

    # Use a no-op approval controller since we're handling approvals via deferred mechanism
    no_op_controller = ApprovalController(mode="approve_all")

    prep = _prepare_worker_context(
        registry=registry,
        worker=worker,
        input_data=input_data,
        attachments=attachments,
        caller_effective_model=caller_effective_model,
        cli_model=cli_model,
        creation_defaults=creation_defaults,
        approval_controller=no_op_controller,
        message_callback=message_callback,
    )

    # Prepare agent execution context
    exec_ctx = prepare_agent_execution(
        prep.definition, input_data, prep.context, prep.output_model
    )

    # Create Agent
    agent = Agent(**exec_ctx.agent_kwargs)

    # Run the deferred tool loop
    message_history = None
    deferred_results = None
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Run agent (first run with prompt, subsequent runs with message_history)
        if message_history is None:
            run_result = await agent.run(
                exec_ctx.prompt,
                deps=prep.context,
                event_stream_handler=exec_ctx.event_handler,
            )
        else:
            run_result = await agent.run(
                message_history=message_history,
                deferred_tool_results=deferred_results,
                deps=prep.context,
                event_stream_handler=exec_ctx.event_handler,
            )

        # Check if we got deferred tool requests
        output = run_result.output
        if isinstance(output, DeferredToolRequests):
            logger.debug(
                f"Deferred tool requests: {len(output.approvals)} approvals, "
                f"{len(output.calls)} external calls"
            )

            # Handle approval requests
            if output.approvals and approval_handler:
                approval_results = await approval_handler(output)
                message_history = run_result.all_messages()
                deferred_results = approval_results
                continue
            elif output.approvals:
                # No handler provided - auto-deny all approvals
                logger.warning("No approval_handler provided, denying all approvals")
                deferred_results = DeferredToolResults(
                    approvals={
                        call.tool_call_id: ToolDenied(message="No approval handler configured")
                        for call in output.approvals
                    }
                )
                message_history = run_result.all_messages()
                continue

            # Handle external/background calls
            if output.calls and call_handler:
                call_results = await call_handler(output)
                message_history = run_result.all_messages()
                deferred_results = call_results
                continue
            elif output.calls:
                # No handler provided - return error to model
                logger.warning("No call_handler provided, returning errors for external calls")
                deferred_results = DeferredToolResults(
                    calls={
                        call.tool_call_id: {"error": "No external call handler configured"}
                        for call in output.calls
                    }
                )
                message_history = run_result.all_messages()
                continue

        # Normal completion - not a DeferredToolRequests
        if exec_ctx.emit_status is not None and exec_ctx.started_at is not None:
            from time import perf_counter
            exec_ctx.emit_status("end", duration=round(perf_counter() - exec_ctx.started_at, 2))

        messages = run_result.all_messages() if hasattr(run_result, 'all_messages') else []
        return _handle_result((output, messages), prep.output_model)

    raise RuntimeError(
        f"Deferred tool loop exceeded max_iterations ({max_iterations}). "
        "This may indicate an infinite loop in tool execution."
    )
