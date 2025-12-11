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
    WorkerContext,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRunResult,
    WorkerSpec,
)

logger = logging.getLogger(__name__)


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
    cli_model: Optional[str],
    program_model: Optional[str],
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
    # Resolution: cli_model > worker.model > program_model > env var
    # All validated against compatible_models
    # ModelCompatibilityError propagates immediately (user error)
    # NoModelError is deferred to execution (backward compat with custom agent_runners)
    effective_model: Optional[str] = None
    try:
        effective_model = select_model(
            worker_model=definition.model,
            cli_model=cli_model,
            program_model=program_model,
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
    """Delegate to another worker (sync version).

    The delegated worker resolves its own model via the standard precedence:
    cli_model > worker.model > program_model > LLM_DO_MODEL env var.
    """
    _check_delegation_allowed(caller_context, worker)
    # Get program_model from registry if available
    program_model = None
    if caller_context.registry and hasattr(caller_context.registry, 'program_config'):
        pc = caller_context.registry.program_config
        if pc:
            program_model = pc.model
    return run_worker(
        registry=registry,
        worker=worker,
        input_data=input_data,
        program_model=program_model,
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

    The delegated worker resolves its own model via the standard precedence:
    cli_model > worker.model > program_model > LLM_DO_MODEL env var.

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
    # Get program_model from registry if available
    program_model = None
    if caller_context.registry and hasattr(caller_context.registry, 'program_config'):
        pc = caller_context.registry.program_config
        if pc:
            program_model = pc.model
    return await run_worker_async(
        registry=registry,
        worker=worker,
        input_data=input_data,
        program_model=program_model,
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
    cli_model: Optional[str] = None,
    program_model: Optional[str] = None,
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

    Model resolution order (highest to lowest priority):
    1. cli_model (--model flag)
    2. worker.model (from worker definition)
    3. program_model (from program.yaml)
    4. LLM_DO_MODEL environment variable

    Args:
        registry: Source for worker definitions.
        worker: Name of the worker to run.
        input_data: Input payload for the worker.
        attachments: Optional files to expose to the worker.
        cli_model: Model from --model CLI flag (highest priority override).
        program_model: Model from program.yaml config.
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
        cli_model=cli_model,
        program_model=program_model,
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
    cli_model: Optional[str] = None,
    program_model: Optional[str] = None,
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

    Model resolution order (highest to lowest priority):
    1. cli_model (--model flag)
    2. worker.model (from worker definition)
    3. program_model (from program.yaml)
    4. LLM_DO_MODEL environment variable

    Args:
        registry: Source for worker definitions.
        worker: Name of the worker to run.
        input_data: Input payload for the worker.
        attachments: Optional files to expose to the worker.
        cli_model: Model from --model CLI flag (highest priority override).
        program_model: Model from program.yaml config.
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
        cli_model=cli_model,
        program_model=program_model,
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
