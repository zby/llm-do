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
from .tool_context import get_context_param
from .tool_registry import ToolRegistry
from pydantic_ai_blocking_approval import ApprovalController
from .attachments import AttachmentInput, AttachmentPayload
from .types import (
    MessageCallback,
    ModelLike,
    ToolContext,
    ToolExecutionContext,
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


def _normalize_attachments(
    attachments: Optional[Sequence[AttachmentInput]],
) -> List[AttachmentPayload]:
    """Normalize attachments to payloads (no policy validation)."""
    attachment_payloads: List[AttachmentPayload] = []
    if not attachments:
        return attachment_payloads

    for item in attachments:
        if isinstance(item, AttachmentPayload):
            attachment_payloads.append(item)
            continue

        display_name = str(item)
        path = Path(item).expanduser().resolve()
        attachment_payloads.append(
            AttachmentPayload(path=path, display_name=display_name)
        )

    return attachment_payloads


def _prepare_worker_context(
    *,
    registry: Any,
    worker: str,
    attachments: Optional[Sequence[AttachmentInput]],
    cli_model: Optional[ModelLike],
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

    attachment_payloads = _normalize_attachments(attachments)

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


async def _invoke_code_tool(
    func: Callable[..., Any],
    *,
    input_data: Any,
    ctx: ToolContext,
) -> Any:
    """Invoke a code tool with optional context injection."""
    context_param = get_context_param(func)
    sig = inspect.signature(func)

    if context_param and context_param not in sig.parameters:
        raise ValueError(
            f"Tool '{func.__name__}' is marked with @tool_context "
            f"but does not accept parameter '{context_param}'."
        )
    if context_param:
        ctx_param = sig.parameters[context_param]
        if ctx_param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            raise ValueError(
                f"Tool '{func.__name__}' uses an unsupported context parameter "
                f"kind ({ctx_param.kind}). Use a keyword-capable parameter for "
                f"'{context_param}'."
            )

    params = [param for name, param in sig.parameters.items() if name != context_param]
    args: list[Any] = []
    kwargs: dict[str, Any] = {}

    if context_param:
        kwargs[context_param] = ctx

    if len(params) == 0:
        if input_data not in (None, {}, ""):
            raise ValueError(
                f"Tool '{func.__name__}' does not accept input "
                "but input_data was provided."
            )
    elif len(params) == 1:
        param = params[0]
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            if not isinstance(input_data, dict):
                raise ValueError(
                    f"Tool '{func.__name__}' expects keyword arguments; "
                    "pass a dict for input_data."
                )
            if context_param and context_param in input_data:
                raise ValueError(
                    f"Tool '{func.__name__}' received input for injected "
                    f"context parameter '{context_param}'."
                )
            kwargs.update(input_data)
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            kwargs[param.name] = input_data
        else:
            if context_param:
                ctx_param = sig.parameters[context_param]
                order = list(sig.parameters.keys())
                ctx_precedes = (
                    ctx_param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
                    and order.index(context_param) < order.index(param.name)
                )
                if ctx_precedes:
                    if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                        raise ValueError(
                            f"Tool '{func.__name__}' has a positional-only "
                            f"parameter ('{param.name}') before the injected "
                            f"context '{context_param}'. Use keyword-capable "
                            "parameters or move the context parameter after "
                            "the input."
                        )
                    if param.kind == inspect.Parameter.VAR_POSITIONAL:
                        raise ValueError(
                            f"Tool '{func.__name__}' cannot accept *args when "
                            f"context '{context_param}' precedes it. Use a "
                            "keyword-only context parameter or move context "
                            "after the input."
                        )
                    kwargs[param.name] = input_data
                else:
                    args.append(input_data)
            else:
                args.append(input_data)
    else:
        positional_only = [
            param.name
            for param in params
            if param.kind == inspect.Parameter.POSITIONAL_ONLY
        ]
        if positional_only:
            names = ", ".join(positional_only)
            raise ValueError(
                f"Tool '{func.__name__}' has positional-only parameters "
                f"({names}). Use a single input parameter or refactor to "
                "keyword-capable parameters."
            )
        if not isinstance(input_data, dict):
            raise ValueError(
                f"Tool '{func.__name__}' expects multiple inputs; "
                "pass a dict for input_data."
            )
        if context_param and context_param in input_data:
            raise ValueError(
                f"Tool '{func.__name__}' received input for injected "
                f"context parameter '{context_param}'."
            )
        kwargs.update(input_data)

    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return func(*args, **kwargs)


async def call_tool_async(
    *,
    registry: Any,  # WorkerRegistry - avoid circular import
    tool: str,
    input_data: Any,
    caller_context: ToolContext,
) -> Any:
    """Call a tool by name (code or worker).

    For worker tools, input_data can be:
    - A string: passed directly as input
    - A dict with "input" and optional "attachments" keys:
      {"input": "...", "attachments": ["path1.pdf", "path2.pdf"]}
    """
    tool_registry = ToolRegistry(registry)
    resolved = tool_registry.find_tool(tool)

    if resolved.kind == "worker":
        # Extract attachments from dict input if present
        attachments = None
        worker_input = input_data
        if isinstance(input_data, dict):
            attachments = input_data.get("attachments")
            # If dict has "input" key, use that as the worker input
            if "input" in input_data:
                worker_input = input_data["input"]

        result = await call_worker_async(
            registry=registry,
            worker=tool,
            input_data=worker_input,
            caller_context=caller_context,
            attachments=attachments,
        )
        return result.output

    return await _invoke_code_tool(
        resolved.handler,
        input_data=input_data,
        ctx=caller_context,
    )


# ---------------------------------------------------------------------------
# Worker delegation
# ---------------------------------------------------------------------------
async def call_worker_async(
    registry: Any,  # WorkerRegistry - avoid circular import
    worker: str,
    input_data: Any,
    *,
    caller_context: ToolContext,
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
        caller_context: Context from the calling tool/worker (propagates depth and approvals).
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
            (project, built-in, or target output_dir) and force=False.
    """
    # Use provided output_dir or fall back to registry's generated_dir
    target_dir = Path(output_dir) if output_dir else registry.generated_dir

    # Generated workers are directories: {target_dir}/{name}/worker.worker
    worker_dir = target_dir / spec.name
    path = worker_dir / "worker.worker"

    # Check for conflicts - never overwrite without force
    if not force:
        # Check if worker exists in the target location
        if path.exists():
            raise FileExistsError(
                f"Worker '{spec.name}' already exists at {path}. "
                "Use a different name or remove the existing worker."
            )
        # Also check project workers and built-ins (but not default generated_dir
        # when using custom output_dir)
        if output_dir:
            # Custom output_dir: only check project and built-in workers
            # (skip registry.worker_exists which checks default generated_dir)
            from .registry import WorkerRegistry
            builtin_simple = Path(__file__).parent / "workers" / f"{spec.name}.worker"
            builtin_dir = Path(__file__).parent / "workers" / spec.name / "worker.worker"
            project_simple = registry.root / f"{spec.name}.worker"
            project_dir = registry.root / spec.name / "worker.worker"
            for check_path in [builtin_simple, builtin_dir, project_simple, project_dir]:
                if check_path.exists():
                    raise FileExistsError(
                        f"Worker '{spec.name}' already exists at {check_path}. "
                        "Use a different name."
                    )
        else:
            # Default behavior: use registry.worker_exists
            if registry.worker_exists(spec.name):
                raise FileExistsError(
                    f"Worker '{spec.name}' already exists. "
                    "Use a different name or remove the existing worker."
                )

    definition = defaults.expand_spec(spec)

    registry.save_definition(definition, force=force, path=path)
    registry.register_generated(spec.name)
    return definition


# ---------------------------------------------------------------------------
# Main worker execution (sync and async)
# ---------------------------------------------------------------------------


async def run_tool_async(
    *,
    registry: Any,  # WorkerRegistry - avoid circular import
    tool: str,
    input_data: Any,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    message_history: Optional[List[Any]] = None,
    cli_model: Optional[ModelLike] = None,
    creation_defaults: Optional[WorkerCreationDefaults] = None,
    agent_runner: Optional[Callable] = None,
    approval_controller: Optional[ApprovalController] = None,
    message_callback: Optional[MessageCallback] = None,
    depth: int = 0,
    cost_tracker: Optional[Any] = None,
) -> WorkerRunResult:
    """Execute a tool by name (async version).

    Code tools are invoked directly with a ToolExecutionContext.
    Worker tools delegate to run_worker_async.
    """
    if approval_controller is None:
        approval_controller = ApprovalController(mode="approve_all")

    tool_registry = ToolRegistry(registry)
    resolved = tool_registry.find_tool(tool)

    if resolved.kind == "worker":
        return await run_worker_async(
            registry=registry,
            worker=tool,
            input_data=input_data,
            attachments=attachments,
            message_history=message_history,
            cli_model=cli_model,
            creation_defaults=creation_defaults,
            agent_runner=agent_runner,
            approval_controller=approval_controller,
            message_callback=message_callback,
            depth=depth,
            cost_tracker=cost_tracker,
        )

    defaults = creation_defaults or WorkerCreationDefaults()
    attachment_payloads = _normalize_attachments(attachments)

    context = ToolExecutionContext(
        registry=registry,
        approval_controller=approval_controller,
        creation_defaults=defaults,
        message_callback=message_callback,
        cli_model=cli_model,
        attachments=attachment_payloads,
        depth=depth,
        cost_tracker=cost_tracker,
    )

    output = await _invoke_code_tool(
        resolved.handler,
        input_data=input_data,
        ctx=context,
    )

    return WorkerRunResult(output=output, messages=[])


async def run_worker_async(
    *,
    registry: Any,  # WorkerRegistry - avoid circular import
    worker: str,
    input_data: Any,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    message_history: Optional[List[Any]] = None,
    cli_model: Optional[ModelLike] = None,
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
        message_history: Optional list of prior model messages for conversation context.
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
            prep.definition,
            input_data,
            prep.context,
            prep.output_model,
            message_history=message_history,
        )
    else:
        # Support both sync and async agent runners (including wrapped coroutines)
        result = agent_runner(prep.definition, input_data, prep.context, prep.output_model)
        if inspect.isawaitable(result):
            result = await result

    return _handle_result(result, prep.output_model)
