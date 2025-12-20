"""Runtime orchestration for llm-do workers.

This module provides the core async runtime implementation:
- Agent execution (async)
- Worker delegation and creation
- Tool registration and execution
- Approval and permission enforcement
- Context preparation and lifecycle management
"""
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Type

from pydantic import BaseModel

from .execution import default_agent_runner_async
from .model_compat import select_model, NoModelError
from pydantic_ai_blocking_approval import ApprovalController
from .attachments import AttachmentInput, AttachmentPayload
from .types import (
    MessageCallback,
    WorkerContext,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRunResult,
    WorkerSpec,
)

logger = logging.getLogger(__name__)

# Maximum nesting depth for worker calls (prevents infinite recursion)
MAX_WORKER_DEPTH = 5


# ---------------------------------------------------------------------------
# Helper dataclasses
# ---------------------------------------------------------------------------


@dataclass
class _WorkerExecutionPrep:
    """Prepared context and metadata for worker execution."""
    context: WorkerContext
    definition: WorkerDefinition
    output_model: Optional[Type[BaseModel]]


def _prepare_worker_context(
    *,
    registry: Any,
    worker: str,
    attachments: Optional[Sequence[AttachmentInput]],
    cli_model: Optional[str],
    creation_defaults: Optional[WorkerCreationDefaults],
    approval_controller: ApprovalController,
    message_callback: Optional[MessageCallback],
    depth: int = 0,
    cost_tracker: Optional[Any] = None,
) -> _WorkerExecutionPrep:
    """Prepare worker context and dependencies (shared by async entrypoints).

    This extracts all the common setup logic used by async entrypoints,
    reducing duplication between call sites.
    """
    definition = registry.load_definition(worker)
    custom_tools_path = registry.find_custom_tools(worker)

    defaults = creation_defaults or WorkerCreationDefaults()

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
    if attachment_payloads:
        definition.attachment_policy.validate_paths([payload.path for payload in attachment_payloads])

    # Select model with compatibility validation
    # Resolution: cli_model > worker.model > env var
    # All validated against compatible_models
    # ModelCompatibilityError propagates immediately (user error)
    # NoModelError is deferred to execution (backward compat with custom agent_runners)
    effective_model: Optional[str] = None
    try:
        effective_model = select_model(
            worker_model=definition.model,
            cli_model=cli_model,
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
        cli_model=cli_model,
        # Nesting control
        depth=depth,
        cost_tracker=cost_tracker,
        # Delegation
        registry=registry,
        creation_defaults=defaults,
        # I/O
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

    The cli_model from the caller is propagated to the delegated worker,
    which then resolves its model via the standard precedence:
    cli_model > worker.model > LLM_DO_MODEL env var.

    Args:
        registry: Source for worker definitions.
        worker: Name of the worker to delegate to.
        input_data: Input payload for the delegated worker.
        caller_context: Context from the calling worker (propagates depth and approvals).
        attachments: Optional files to pass to the delegated worker.
        agent_runner: Optional async agent runner (defaults to async PydanticAI).

    Returns:
        WorkerRunResult from the delegated worker.

    Raises:
        RecursionError: If max worker depth would be exceeded.
    """

    # Check depth limit before executing nested worker
    if caller_context.depth >= MAX_WORKER_DEPTH:
        raise RecursionError(
            f"Maximum worker nesting depth ({MAX_WORKER_DEPTH}) exceeded. "
            f"Current depth: {caller_context.depth}, attempting to call: {worker}"
        )

    return await run_worker_async(
        registry=registry,
        worker=worker,
        input_data=input_data,
        attachments=attachments,
        cli_model=caller_context.cli_model,
        creation_defaults=caller_context.creation_defaults,
        agent_runner=agent_runner,
        message_callback=caller_context.message_callback,
        approval_controller=caller_context.approval_controller,
        depth=caller_context.depth + 1,
        cost_tracker=caller_context.cost_tracker,
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
    output_dir: Optional[Path] = None,
) -> WorkerDefinition:
    """Create and persist a new worker definition.

    Generated workers are saved to the specified output_dir (or registry.generated_dir
    if not specified) and registered with the registry so they can be found in this session.

    Args:
        registry: WorkerRegistry instance
        spec: Worker specification with name, instructions, etc.
        defaults: Default values for worker creation
        force: If True, overwrite existing workers
        output_dir: Directory to save the worker to (default: registry.generated_dir)

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

    # Use provided output_dir or fall back to registry's generated_dir
    target_dir = Path(output_dir) if output_dir else registry.generated_dir

    # Generated workers are directories: {target_dir}/{name}/worker.worker
    worker_dir = target_dir / spec.name
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
    creation_defaults: Optional[WorkerCreationDefaults] = None,
    agent_runner: Optional[Callable] = None,
    approval_controller: Optional[ApprovalController] = None,
    message_callback: Optional[MessageCallback] = None,
    depth: int = 0,
    cost_tracker: Optional[Any] = None,
) -> WorkerRunResult:
    """Execute a worker by name (async version).

    This is the async entry point for running workers. It handles:
    1. Loading the worker definition.
    2. Setting up the runtime environment (tools, approvals).
    3. Creating the execution context.
    4. Awaiting the async agent runner.

    Model resolution order (highest to lowest priority):
    1. cli_model (--model flag)
    2. worker.model (from worker definition)
    3. LLM_DO_MODEL environment variable

    Args:
        registry: Source for worker definitions.
        worker: Name of the worker to run.
        input_data: Input payload for the worker.
        attachments: Optional files to expose to the worker.
        cli_model: Model from --model CLI flag (highest priority override).
        creation_defaults: Defaults for any new workers created during this run.
        agent_runner: Optional async strategy for executing the agent (defaults to async PydanticAI).
        approval_controller: Controller for tool approval (defaults to approve-all mode).
        message_callback: Callback for streaming events and progress updates.
        depth: Current nesting depth for nested worker calls (0 = top-level).
        cost_tracker: Optional cost tracking across nested calls (future enhancement).

    Returns:
        WorkerRunResult containing the final output and message history.
    """
    if approval_controller is None:
        approval_controller = ApprovalController(mode="approve_all")

    prep = _prepare_worker_context(
        registry=registry,
        worker=worker,
        attachments=attachments,
        cli_model=cli_model,
        creation_defaults=creation_defaults,
        approval_controller=approval_controller,
        message_callback=message_callback,
        depth=depth,
        cost_tracker=cost_tracker,
    )

    # Use the provided agent_runner or default to the async version
    # Delegator/creator are now accessed via prep.context.delegator/.creator
    if agent_runner is None:
        result = await default_agent_runner_async(
            prep.definition, input_data, prep.context, prep.output_model
        )
    else:
        # Support both sync and async agent runners (including wrapped coroutines)
        result = agent_runner(prep.definition, input_data, prep.context, prep.output_model)
        if inspect.isawaitable(result):
            result = await result

    return _handle_result(result, prep.output_model)
