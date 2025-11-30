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
from .tool_approval import (
    ApprovalController,
    ApprovalDecision,
    ApprovalRequest,
)
from .protocols import WorkerCreator, WorkerDelegator
from .sandbox import AttachmentInput, AttachmentPayload
from .worker_sandbox import AttachmentValidator, Sandbox, SandboxConfig
from .tools import register_worker_tools
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
# Helper dataclasses
# ---------------------------------------------------------------------------


@dataclass
class _WorkerExecutionPrep:
    """Prepared context and metadata for worker execution."""
    context: WorkerContext
    definition: WorkerDefinition
    output_model: Optional[Type[BaseModel]]
    register_tools_fn: Callable
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

    if definition.sandbox is not None:
        # Worker has explicit sandbox config
        new_sandbox = Sandbox(definition.sandbox, base_path=registry.root)
        attachment_validator = AttachmentValidator(new_sandbox)
        logger.debug(f"Using unified sandbox for worker '{worker}'")
    elif defaults.default_sandbox is not None:
        # Use default sandbox from creation defaults
        new_sandbox = Sandbox(defaults.default_sandbox, base_path=registry.root)
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

    effective_model = definition.model or caller_effective_model or cli_model

    # Resolve shell_cwd: if worker specifies one, make it absolute (relative to registry.root)
    resolved_shell_cwd: Optional[Path] = None
    if definition.shell_cwd is not None:
        cwd_path = Path(definition.shell_cwd)
        if cwd_path.is_absolute():
            resolved_shell_cwd = cwd_path
        else:
            resolved_shell_cwd = (Path(registry.root) / cwd_path).resolve()

    context = WorkerContext(
        registry=registry,
        worker=definition,
        attachment_validator=attachment_validator,
        creation_defaults=defaults,
        effective_model=effective_model,
        approval_controller=approval_controller,
        sandbox=new_sandbox,
        attachments=attachment_payloads,
        message_callback=message_callback,
        custom_tools_path=custom_tools_path,
        shell_cwd=resolved_shell_cwd,
    )

    output_model = registry.resolve_output_schema(definition)

    # Create a closure for tool registration using protocol implementations
    def _register_tools_for_worker(agent, ctx):
        delegator = RuntimeDelegator(ctx)
        creator = RuntimeCreator(ctx)
        register_worker_tools(agent, ctx, delegator, creator)

    return _WorkerExecutionPrep(
        context=context,
        definition=definition,
        output_model=output_model,
        register_tools_fn=_register_tools_for_worker,
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
# Protocol implementations for dependency injection
# ---------------------------------------------------------------------------


class RuntimeDelegator:
    """Concrete implementation of WorkerDelegator protocol.

    This handles worker delegation with approval enforcement and attachment validation.
    Injected into tools to enable recursive worker calls without circular imports.
    """

    def __init__(self, context: WorkerContext):
        self.context = context

    def _check_approval(self, tool_name: str, payload: Dict[str, Any], description: str) -> None:
        """Check approval using the unified ApprovalController.

        Raises PermissionError if approval is denied.
        """
        request = ApprovalRequest(
            tool_name=tool_name,
            description=description,
            tool_args=payload,
        )
        decision = self.context.approval_controller.request_approval_sync(request)
        if not decision.approved:
            note = f": {decision.note}" if decision.note else ""
            raise PermissionError(f"Approval denied for {tool_name}{note}")

    async def call_async(
        self,
        worker: str,
        input_data: Any = None,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        """Async worker delegation with approval enforcement."""
        resolved_attachments: List[Path]
        attachment_metadata: List[Dict[str, Any]]
        if attachments:
            resolved_attachments, attachment_metadata = self.context.validate_attachments(attachments)
        else:
            resolved_attachments, attachment_metadata = ([], [])

        # Check sandbox.read approval for each attachment before sharing
        # Done after validation so we have full metadata (sandbox, path, size)
        for meta in attachment_metadata:
            self._check_approval(
                "sandbox.read",
                {"path": f"{meta['sandbox']}/{meta['path']}", "bytes": meta["bytes"], "target_worker": worker},
                f"Share file '{meta['sandbox']}/{meta['path']}' with worker '{worker}'",
            )

        attachment_payloads: Optional[List[AttachmentPayload]] = None
        if resolved_attachments:
            attachment_payloads = [
                AttachmentPayload(
                    path=path,
                    display_name=f"{meta['sandbox']}/{meta['path']}",
                )
                for path, meta in zip(resolved_attachments, attachment_metadata)
            ]

        payload: Dict[str, Any] = {"worker": worker}
        if attachment_metadata:
            payload["attachments"] = attachment_metadata

        # Check worker.call approval
        self._check_approval(
            "worker.call",
            payload,
            f"Delegate to worker '{worker}'",
        )

        # Now execute async
        result = await call_worker_async(
            registry=self.context.registry,
            worker=worker,
            input_data=input_data,
            caller_context=self.context,
            attachments=attachment_payloads,
        )
        return result.output

    def call_sync(
        self,
        worker: str,
        input_data: Any = None,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        """Sync worker delegation with approval enforcement."""
        resolved_attachments: List[Path]
        attachment_metadata: List[Dict[str, Any]]
        if attachments:
            resolved_attachments, attachment_metadata = self.context.validate_attachments(attachments)
        else:
            resolved_attachments, attachment_metadata = ([], [])

        # Check sandbox.read approval for each attachment before sharing
        # Done after validation so we have full metadata (sandbox, path, size)
        for meta in attachment_metadata:
            self._check_approval(
                "sandbox.read",
                {"path": f"{meta['sandbox']}/{meta['path']}", "bytes": meta["bytes"], "target_worker": worker},
                f"Share file '{meta['sandbox']}/{meta['path']}' with worker '{worker}'",
            )

        attachment_payloads: Optional[List[AttachmentPayload]] = None
        if resolved_attachments:
            attachment_payloads = [
                AttachmentPayload(
                    path=path,
                    display_name=f"{meta['sandbox']}/{meta['path']}",
                )
                for path, meta in zip(resolved_attachments, attachment_metadata)
            ]

        payload: Dict[str, Any] = {"worker": worker}
        if attachment_metadata:
            payload["attachments"] = attachment_metadata

        # Check worker.call approval
        self._check_approval(
            "worker.call",
            payload,
            f"Delegate to worker '{worker}'",
        )

        # Execute
        result = call_worker(
            registry=self.context.registry,
            worker=worker,
            input_data=input_data,
            caller_context=self.context,
            attachments=attachment_payloads,
        )
        return result.output


class RuntimeCreator:
    """Concrete implementation of WorkerCreator protocol.

    Handles worker creation with approval enforcement.
    Injected into tools to enable the worker_create tool.
    """

    def __init__(self, context: WorkerContext):
        self.context = context

    def create(
        self,
        name: str,
        instructions: str,
        description: Optional[str] = None,
        model: Optional[str] = None,
        output_schema_ref: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Create worker with approval enforcement."""
        payload = {"worker": name}

        # Check worker.create approval
        request = ApprovalRequest(
            tool_name="worker.create",
            description=f"Create new worker '{name}'",
            tool_args=payload,
        )
        decision = self.context.approval_controller.request_approval_sync(request)
        if not decision.approved:
            note = f": {decision.note}" if decision.note else ""
            raise PermissionError(f"Approval denied for worker.create{note}")

        # Execute
        spec = WorkerSpec(
            name=name,
            instructions=instructions,
            description=description,
            model=model,
            output_schema_ref=output_schema_ref,
        )
        created = create_worker(
            registry=self.context.registry,
            spec=spec,
            defaults=self.context.creation_defaults,
            force=force,
        )
        return created.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Worker delegation
# ---------------------------------------------------------------------------


def _check_delegation_allowed(caller_context: WorkerContext, worker: str) -> None:
    """Check if delegation to a worker is allowed (shared by sync and async)."""
    allowed = caller_context.worker.allow_workers
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
    if agent_runner is None:
        result = await default_agent_runner_async(
            prep.definition, input_data, prep.context, prep.output_model,
            register_tools_fn=prep.register_tools_fn
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
    # context.
    if agent_runner is None:
        result = default_agent_runner(
            prep.definition, input_data, prep.context, prep.output_model,
            register_tools_fn=prep.register_tools_fn
        )
    else:
        result = agent_runner(prep.definition, input_data, prep.context, prep.output_model)

    return _handle_result(result, prep.output_model)
