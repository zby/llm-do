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

from .protocols import FileSandbox, WorkerCreator, WorkerDelegator
from .shell import (
    ShellBlockedError,
    execute_shell,
    enhance_error_with_sandbox_context,
    match_shell_rules,
    parse_command,
)
from .types import ShellResult, WorkerContext

logger = logging.getLogger(__name__)


def register_worker_tools(
    agent: Agent,
    context: WorkerContext,
    delegator: WorkerDelegator,
    creator: WorkerCreator,
    sandbox: Optional[FileSandbox] = None,
) -> None:
    """Register all tools for a worker.

    Args:
        agent: PydanticAI agent to register tools with
        context: Worker execution context
        delegator: Implementation of worker delegation (DI)
        creator: Implementation of worker creation (DI)
        sandbox: Optional FileSandbox instance (new unified sandbox).
                 If not provided, falls back to legacy sandbox_toolset.

    Registers:
    1. Sandbox tools (list, read_text, write_text)
    2. Worker delegation tool (worker_call)
    3. Worker creation tool (worker_create)
    4. Custom tools from tools.py if available
    """

    # Register built-in sandbox tools
    if sandbox is not None:
        _register_new_sandbox_tools(agent, context, file_sandbox=sandbox)
    else:
        _register_sandbox_tools(agent, context)

    # Register shell tool if enabled
    _register_shell_tool(agent, context, sandbox)

    # Register worker delegation/creation tools with injected implementations
    _register_worker_delegation_tools(agent, context, delegator, creator)

    # Load and register custom tools if available
    if context.custom_tools_path:
        load_custom_tools(agent, context)


def _register_sandbox_tools(agent: Agent, context: WorkerContext) -> None:
    """Register legacy sandbox file operations.

    These tools use the old sandbox_toolset API with explicit sandbox names.
    Kept for backward compatibility.
    """

    @agent.tool(
        name="sandbox_list",
        description="List files within a sandbox using a glob pattern"
    )
    def sandbox_list(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        pattern: str = "**/*",
    ) -> List[str]:
        return ctx.deps.sandbox_toolset.list(sandbox, pattern)

    @agent.tool(
        name="sandbox_read_text",
        description="Read UTF-8 text from a sandboxed file. "
                    "Do not use this on binary files (PDFs, images, etc) - "
                    "pass them as attachments instead."
    )
    def sandbox_read_text(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        path: str,
        *,
        max_chars: int = 200_000,
    ) -> str:
        return ctx.deps.sandbox_toolset.read_text(sandbox, path, max_chars=max_chars)

    @agent.tool(
        name="sandbox_write_text",
        description="Write UTF-8 text to a sandboxed file"
    )
    def sandbox_write_text(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        path: str,
        content: str,
    ) -> Optional[str]:
        return ctx.deps.sandbox_toolset.write_text(sandbox, path, content)


def _register_new_sandbox_tools(
    agent: Agent,
    context: WorkerContext,
    file_sandbox: FileSandbox,
) -> None:
    """Register new sandbox file operations using FileSandbox protocol.

    These tools use the new unified sandbox API with path format "sandbox_name/relative/path".
    """

    @agent.tool(
        name="read_file",
        description="Read a text file from the sandbox. "
                    "Path format: 'sandbox_name/relative/path'. "
                    "Do not use this on binary files (PDFs, images, etc) - "
                    "pass them as attachments instead."
    )
    def read_file(
        ctx: RunContext[WorkerContext],
        path: str,
        max_chars: int = 200_000,
    ) -> str:
        return file_sandbox.read(path, max_chars=max_chars)

    @agent.tool(
        name="write_file",
        description="Write a text file to the sandbox. "
                    "Path format: 'sandbox_name/relative/path'."
    )
    def write_file(
        ctx: RunContext[WorkerContext],
        path: str,
        content: str,
    ) -> str:
        # Route through approval controller for writes
        return ctx.deps.approval_controller.maybe_run(
            "sandbox.write",
            {"path": path},
            lambda: file_sandbox.write(path, content),
        )

    @agent.tool(
        name="list_files",
        description="List files in the sandbox matching a glob pattern. "
                    "Path format: 'sandbox_name' or 'sandbox_name/subdir'. "
                    "Use '.' to list all sandboxes."
    )
    def list_files(
        ctx: RunContext[WorkerContext],
        path: str = ".",
        pattern: str = "**/*",
    ) -> List[str]:
        return file_sandbox.list_files(path, pattern)

    # Also register legacy tool names as aliases for backward compatibility
    # Note: parameter names must match old API (sandbox, not sandbox_name)
    @agent.tool(
        name="sandbox_list",
        description="[DEPRECATED: Use list_files instead] List files within a sandbox"
    )
    def sandbox_list_compat(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        pattern: str = "**/*",
    ) -> List[str]:
        return file_sandbox.list_files(sandbox, pattern)

    @agent.tool(
        name="sandbox_read_text",
        description="[DEPRECATED: Use read_file instead] Read UTF-8 text from a sandboxed file"
    )
    def sandbox_read_text_compat(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        path: str,
        max_chars: int = 200_000,
    ) -> str:
        return file_sandbox.read(f"{sandbox}/{path}", max_chars=max_chars)

    @agent.tool(
        name="sandbox_write_text",
        description="[DEPRECATED: Use write_file instead] Write UTF-8 text to a sandboxed file"
    )
    def sandbox_write_text_compat(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        path: str,
        content: str,
    ) -> str:
        # Route through approval controller for writes
        full_path = f"{sandbox}/{path}"
        return ctx.deps.approval_controller.maybe_run(
            "sandbox.write",
            {"sandbox": sandbox, "path": path},
            lambda: file_sandbox.write(full_path, content),
        )


def _register_shell_tool(
    agent: Agent,
    context: WorkerContext,
    file_sandbox: Optional[FileSandbox],
) -> None:
    """Register the shell tool for executing commands.

    The shell tool:
    1. Checks if shell is enabled via tool_rules
    2. Matches command against shell_rules for approval decision
    3. Routes through approval controller
    4. Executes command and returns result
    """
    # Check if shell is enabled via tool_rules
    shell_rule = context.worker.tool_rules.get("shell")
    if shell_rule is not None and not shell_rule.allowed:
        logger.debug(f"Shell tool disabled for worker '{context.worker.name}'")
        return

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
            file_sandbox=file_sandbox,
        )

        # Check if command is allowed
        if not allowed:
            return ShellResult(
                stdout="",
                stderr=f"Command not allowed by shell rules: {command}",
                exit_code=1,
                truncated=False,
            )

        # Determine approval requirement
        # Priority: shell_rules match > shell_default > tool_rules.shell
        if not approval_required:
            # Auto-approved by shell_rules
            pass
        else:
            # Check tool_rules.shell for approval override
            shell_tool_rule = ctx.deps.worker.tool_rules.get("shell")
            if shell_tool_rule is not None and not shell_tool_rule.approval_required:
                approval_required = False

        # Execute with or without approval
        def _execute() -> ShellResult:
            working_dir = Path(ctx.deps.registry.root)
            result = execute_shell(
                command=command,
                working_dir=working_dir,
                timeout=timeout,
            )
            # Enhance errors with sandbox context
            return enhance_error_with_sandbox_context(result, file_sandbox)

        if approval_required:
            # Route through approval controller
            return ctx.deps.approval_controller.maybe_run(
                "shell",
                {"command": command},
                _execute,
            )
        else:
            # Auto-approved
            try:
                return _execute()
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
    Only functions explicitly listed in the worker's tool_rules are registered.
    Each tool call is wrapped with the approval controller to enforce security policies.

    Security guarantees:
    - Only functions listed in definition.tool_rules are registered (allowlist)
    - All tool calls go through approval_controller.maybe_run() (approval enforcement)
    - Tool rules (allowed, approval_required) are respected
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

    # Only register functions that are explicitly allowed in tool_rules
    allowed_tools = {
        name: rule
        for name, rule in context.worker.tool_rules.items()
        if rule.allowed
    }

    if not allowed_tools:
        logger.debug(f"No custom tools allowed in tool_rules for {context.worker.name}")
        return

    # Find and register allowed functions from the module
    for tool_name, tool_rule in allowed_tools.items():
        # Check if this tool exists in the module
        if not hasattr(module, tool_name):
            continue

        obj = getattr(module, tool_name)
        if not (
            callable(obj)
            and inspect.isfunction(obj)
            and obj.__module__ == module.__name__
        ):
            logger.warning(f"Custom tool '{tool_name}' is not a function in {tools_path}")
            continue

        # Wrap the function to enforce approval via the approval controller
        # This ensures tool_rules.approval_required is respected
        def make_wrapped_tool(func, name):
            """Create a wrapped tool that goes through approval controller."""
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

            # Create wrapper function
            def wrapped_tool(ctx, **tool_kwargs):
                """Wrapped custom tool that enforces approval rules."""
                def _invoke():
                    # Call the original function with the tool arguments
                    return func(**tool_kwargs)

                # Use approval controller to enforce tool_rules
                return ctx.deps.approval_controller.maybe_run(
                    name,
                    tool_kwargs,
                    _invoke,
                )

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
            # Create wrapped version that enforces approvals
            wrapped = make_wrapped_tool(obj, tool_name)

            # Register using agent.tool (not tool_plain) since we need RunContext for approval
            agent.tool(
                name=tool_name,
                description=obj.__doc__ or tool_rule.description or f"Custom tool: {tool_name}"
            )(wrapped)

            logger.debug(f"Registered custom tool with approval enforcement: {tool_name}")
        except Exception as e:
            logger.warning(f"Could not register custom tool '{tool_name}': {e}")
