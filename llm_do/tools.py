"""Tool registration for llm-do workers.

This module registers both built-in tools (sandbox_*, worker_*) and
custom tools loaded from workers/{name}/tools.py files.

Uses protocol-based DI to avoid circular imports with runtime.py.
"""
from __future__ import annotations

import inspect
import importlib.util
import logging
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic_ai import Agent
from pydantic_ai.tools import RunContext

from .protocols import WorkerCreator, WorkerDelegator
from .shell import (
    ShellBlockedError,
    execute_shell,
    enhance_error_with_sandbox_context,
    match_shell_rules,
    parse_command,
)
from pydantic_ai_blocking_approval import ApprovalRequest
from .types import ShellResult, WorkerContext

logger = logging.getLogger(__name__)


def register_worker_tools(
    agent: Agent,
    context: WorkerContext,
    delegator: WorkerDelegator,
    creator: WorkerCreator,
) -> None:
    """Register all tools for a worker.

    Args:
        agent: PydanticAI agent to register tools with
        context: Worker execution context
        delegator: Implementation of worker delegation (DI)
        creator: Implementation of worker creation (DI)

    Registers:
    1. Shell tool (if enabled)
    2. Worker delegation tool (worker_call)
    3. Worker creation tool (worker_create)
    4. Custom tools from tools.py if available

    Note: Sandbox tools (read_file, write_file, list_files) are provided
    by the Sandbox toolset passed to the Agent constructor.
    """
    # Register shell tool if enabled
    _register_shell_tool(agent, context)

    # Register worker delegation/creation tools with injected implementations
    _register_worker_delegation_tools(agent, context, delegator, creator)

    # Load and register custom tools if available
    if context.custom_tools_path:
        load_custom_tools(agent, context)


def _register_shell_tool(
    agent: Agent,
    context: WorkerContext,
) -> None:
    """Register the shell tool for executing commands.

    The shell tool:
    1. Matches command against shell_rules for approval decision
    2. Falls back to shell_default if no rule matches
    3. Routes through approval controller if approval required
    4. Executes command and returns result

    To disable shell entirely, use: shell_default: {allowed: false}
    """
    @agent.tool(
        name="shell",
        description="Execute a shell command. Commands are parsed with shlex and "
                    "executed without a shell for security. Shell metacharacters "
                    "(|, >, <, ;, &, `, $() are blocked."
    )
    def shell_tool(
        ctx: RunContext[WorkerContext],
        command: str,
        timeout: int = 30,
    ) -> ShellResult:
        """Execute a shell command.

        Args:
            command: Command to execute (parsed with shlex)
            timeout: Timeout in seconds (default 30, max 300)

        Returns:
            ShellResult with stdout, stderr, exit_code, and truncated flag
        """
        # Enforce timeout limits
        timeout = min(max(timeout, 1), 300)

        # Get worker's shell configuration
        worker = ctx.deps.worker
        shell_rules = worker.shell_rules
        shell_default = worker.shell_default

        # Parse command for rule matching
        try:
            args = parse_command(command)
        except ShellBlockedError as e:
            return ShellResult(
                stdout="",
                stderr=str(e),
                exit_code=1,
                truncated=False,
            )

        # Match against shell_rules
        allowed, approval_required = match_shell_rules(
            command=command,
            args=args,
            rules=shell_rules,
            default=shell_default,
            file_sandbox=ctx.deps.sandbox,
        )

        # Check if command is allowed
        if not allowed:
            return ShellResult(
                stdout="",
                stderr=f"Command not allowed by shell rules: {command}",
                exit_code=1,
                truncated=False,
            )

        # Check approval if required (determined by shell_rules or shell_default)
        if approval_required:
            # Route through approval controller using new pattern
            request = ApprovalRequest(
                tool_name="shell",
                description=f"Execute: {command[:80]}{'...' if len(command) > 80 else ''}",
                tool_args={"command": command},
            )
            decision = ctx.deps.approval_controller.request_approval_sync(request)
            if not decision.approved:
                note = f": {decision.note}" if decision.note else ""
                return ShellResult(
                    stdout="",
                    stderr=f"Approval denied for shell{note}",
                    exit_code=1,
                    truncated=False,
                )

        # Execute command
        try:
            # Determine working directory:
            # 1. If context.shell_cwd is set (from worker.shell_cwd or --set override), use it
            # 2. Otherwise, use current working directory
            working_dir = ctx.deps.shell_cwd if ctx.deps.shell_cwd is not None else Path.cwd()
            result = execute_shell(
                command=command,
                working_dir=working_dir,
                timeout=timeout,
            )
            # Enhance errors with sandbox context
            return enhance_error_with_sandbox_context(result, ctx.deps.sandbox)
        except ShellBlockedError as e:
            return ShellResult(
                stdout="",
                stderr=str(e),
                exit_code=1,
                truncated=False,
            )


def _register_worker_delegation_tools(
    agent: Agent,
    context: WorkerContext,
    delegator: WorkerDelegator,
    creator: WorkerCreator,
) -> None:
    """Register worker_call and worker_create tools using injected implementations.

    This uses dependency injection to avoid circular imports between tools.py
    and runtime.py. The delegator and creator are protocol implementations
    provided by the runtime.
    """

    @agent.tool(
        name="worker_call",
        description="Delegate to another registered worker"
    )
    async def worker_call_tool(
        ctx: RunContext[WorkerContext],
        worker: str,
        input_data: Any = None,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        # Use injected delegator instead of importing call_worker_async
        return await delegator.call_async(worker, input_data, attachments)

    @agent.tool(
        name="worker_create",
        description="Persist a new worker definition using the active profile"
    )
    def worker_create_tool(
        ctx: RunContext[WorkerContext],
        name: str,
        instructions: str,
        description: Optional[str] = None,
        model: Optional[str] = None,
        output_schema_ref: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        # Use injected creator
        return creator.create(
            name=name,
            instructions=instructions,
            description=description,
            model=model,
            output_schema_ref=output_schema_ref,
            force=force,
        )


def load_custom_tools(agent: Agent, context: WorkerContext) -> None:
    """Load and register custom tools from tools.py module.

    Custom tools are functions defined in the tools.py file in the worker's directory.
    Only functions explicitly listed in the worker's custom_tools are registered.

    Approval is determined by whether the function has a check_approval method
    (added via @requires_approval decorator). Functions without the decorator
    execute without approval prompts.

    Security guarantees:
    - Only functions listed in definition.custom_tools are registered (allowlist)
    - Functions with @requires_approval go through approval_controller
    """
    tools_path = context.custom_tools_path
    if not tools_path or not tools_path.exists():
        return

    # Load the module from the file path
    spec = importlib.util.spec_from_file_location(
        f"{context.worker.name}_tools", tools_path
    )
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

    # Only register functions that are explicitly allowed in custom_tools
    allowed_tools = context.worker.custom_tools

    if not allowed_tools:
        logger.debug(f"No custom tools listed for {context.worker.name}")
        return

    # Find and register allowed functions from the module
    for tool_name in allowed_tools:
        # Check if this tool exists in the module
        if not hasattr(module, tool_name):
            logger.warning(f"Custom tool '{tool_name}' not found in {tools_path}")
            continue

        obj = getattr(module, tool_name)
        if not (
            callable(obj)
            and inspect.isfunction(obj)
            and obj.__module__ == module.__name__
        ):
            logger.warning(f"Custom tool '{tool_name}' is not a function in {tools_path}")
            continue

        # Wrap the function to enforce approval via @requires_approval decorator
        def make_wrapped_tool(func, name):
            """Create a wrapped tool that goes through approval controller if decorated."""
            # Get the original function's signature
            orig_sig = inspect.signature(func)
            orig_params = list(orig_sig.parameters.values())

            # Build new parameters list: ctx first, then original params
            new_params = [
                inspect.Parameter(
                    'ctx',
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=RunContext[WorkerContext]
                )
            ]
            # Add copies of original parameters
            for param in orig_params:
                new_params.append(
                    inspect.Parameter(
                        param.name,
                        param.kind,
                        default=param.default,
                        annotation=param.annotation
                    )
                )

            # Create new signature with ctx added
            new_sig = inspect.Signature(
                parameters=new_params,
                return_annotation=orig_sig.return_annotation
            )

            # Check if function has @requires_approval decorator
            has_approval = getattr(func, '_requires_approval', False)

            # Create wrapper function
            def wrapped_tool(ctx, **tool_kwargs):
                """Wrapped custom tool that enforces approval if decorated."""
                # Check if tool has @requires_approval decorator
                if has_approval:
                    request = ApprovalRequest(
                        tool_name=name,
                        tool_args=tool_kwargs,
                        description=f"Custom tool: {name}",
                    )
                    decision = ctx.deps.approval_controller.request_approval_sync(request)
                    if not decision.approved:
                        note = f": {decision.note}" if decision.note else ""
                        raise PermissionError(f"Approval denied for {name}{note}")

                # Call the original function with the tool arguments
                return func(**tool_kwargs)

            # Apply the new signature and preserve metadata
            wrapped_tool.__signature__ = new_sig
            wrapped_tool.__name__ = func.__name__
            wrapped_tool.__doc__ = func.__doc__
            wrapped_tool.__annotations__ = {
                'ctx': RunContext[WorkerContext],
                **func.__annotations__,
                'return': func.__annotations__.get('return', orig_sig.return_annotation)
            }

            return wrapped_tool

        try:
            # Create wrapped version
            wrapped = make_wrapped_tool(obj, tool_name)

            # Register using agent.tool (not tool_plain) since we need RunContext for approval
            agent.tool(
                name=tool_name,
                description=obj.__doc__ or f"Custom tool: {tool_name}"
            )(wrapped)

            logger.debug(f"Registered custom tool: {tool_name}")
        except Exception as e:
            logger.warning(f"Could not register custom tool '{tool_name}': {e}")
