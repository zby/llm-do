"""Agent execution: runs PydanticAI agents with the AgentRuntime."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterable, Literal, Sequence

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import PartDeltaEvent

from .agent_loader import AgentBundle, build_prompt_for_input, load_agents
from .agent_runtime import AgentRuntime, AttachmentResolver, EventCallback
from .approval import (
    ApprovalCallback,
    RunApprovalPolicy,
    resolve_approval_callback,
)
from .args import WorkerArgs
from .event_parser import parse_event
from .events import (
    CompletionEvent,
    ToolCallEvent,
    ToolResultEvent,
    UserMessageEvent,
)
from .toolsets import cleanup_toolsets

if TYPE_CHECKING:
    from pydantic_ai_blocking_approval import ApprovalDecision


async def run_agent(
    agent: Agent[AgentRuntime, Any],
    prompt: str | Sequence[Any],
    *,
    runtime: AgentRuntime,
    agent_name: str | None = None,
) -> Any:
    """Run an agent with the given runtime and prompt.

    Args:
        agent: The PydanticAI agent to run
        prompt: The prompt (string or multipart)
        runtime: The AgentRuntime deps
        agent_name: Optional agent name for event emission

    Returns:
        The agent output
    """
    toolsets = runtime.toolsets_for(agent, agent_name=agent_name)
    result = await agent.run(
        prompt,
        deps=runtime,
        usage=runtime.create_usage(),
        event_stream_handler=runtime.event_stream_handler,
        toolsets=toolsets,
    )
    return result.output


async def run_entry_agent(
    bundle: AgentBundle,
    input_data: Any,
    *,
    runtime: AgentRuntime,
) -> Any:
    """Run the entry agent from a bundle.

    Args:
        bundle: The agent bundle with entry point
        input_data: Input data for the agent
        runtime: The AgentRuntime

    Returns:
        The agent output
    """
    if bundle.entry_name is None:
        raise ValueError("No entry agent found in bundle")

    agent = bundle.agents.get(bundle.entry_name)
    if agent is None:
        raise ValueError(f"Entry agent '{bundle.entry_name}' not found")

    schema_in = bundle.schemas.get(bundle.entry_name)
    prompt = build_prompt_for_input(runtime, input_data, schema_in=schema_in)

    # Emit user message event
    if runtime.on_event is not None:
        runtime.on_event(
            UserMessageEvent(
                worker=bundle.entry_name,
                content=prompt if isinstance(prompt, str) else str(prompt),
            )
        )

    output = await run_agent(
        agent,
        prompt,
        runtime=runtime,
        agent_name=bundle.entry_name,
    )

    # Emit completion event
    if runtime.on_event is not None:
        runtime.on_event(CompletionEvent(worker=bundle.entry_name))

    return output


async def run_with_event_stream(
    agent: Agent[AgentRuntime, Any],
    prompt: str | Sequence[Any],
    *,
    runtime: AgentRuntime,
    agent_name: str,
) -> Any:
    """Run an agent with event stream handling for UI updates.

    Args:
        agent: The PydanticAI agent to run
        prompt: The prompt
        runtime: The AgentRuntime
        agent_name: Name for event emission

    Returns:
        The agent output
    """
    toolsets = runtime.toolsets_for(agent, agent_name=agent_name)
    emitted_tool_events = False

    async def event_stream_handler(
        _: RunContext[AgentRuntime], events: AsyncIterable[Any]
    ) -> None:
        nonlocal emitted_tool_events
        async for event in events:
            if runtime.verbosity < 2 and isinstance(event, PartDeltaEvent):
                continue
            runtime_event = parse_event({
                "worker": agent_name,
                "event": event,
                "depth": runtime.depth,
            })
            if isinstance(runtime_event, (ToolCallEvent, ToolResultEvent)):
                emitted_tool_events = True
            if runtime.on_event is not None:
                runtime.on_event(runtime_event)

    result = await agent.run(
        prompt,
        deps=runtime,
        usage=runtime.create_usage(),
        event_stream_handler=event_stream_handler,
        toolsets=toolsets,
    )

    # Log messages
    runtime.log_messages(agent_name, runtime.depth, list(result.all_messages()))

    return result.output


def build_runtime(
    bundle: AgentBundle,
    *,
    project_root: Path | None = None,
    approval_policy: RunApprovalPolicy | None = None,
    approval_callback: ApprovalCallback | None = None,
    approval_cache: dict[Any, "ApprovalDecision"] | None = None,
    max_depth: int = 5,
    on_event: EventCallback | None = None,
    message_log_callback: Any | None = None,
    verbosity: int = 0,
    return_permission_errors: bool = False,
    attachment_resolver: AttachmentResolver | None = None,
    capability_rules: dict[str, str] | None = None,
    capability_default: str = "needs_approval",
) -> AgentRuntime:
    """Build an AgentRuntime from a bundle.

    Args:
        bundle: The agent bundle
        project_root: Project root for attachments
        approval_policy: Approval policy configuration
        approval_callback: Custom approval callback
        approval_cache: Shared approval cache
        max_depth: Maximum delegation depth
        on_event: Event callback
        message_log_callback: Message logging callback
        verbosity: Verbosity level
        return_permission_errors: Return errors instead of raising
        attachment_resolver: Custom attachment resolver
        capability_rules: Capability-based approval rules
        capability_default: Default capability rule

    Returns:
        Configured AgentRuntime
    """
    # Resolve approval callback
    if approval_policy is None:
        approval_policy = RunApprovalPolicy(
            mode="approve_all",
            approval_callback=approval_callback,
            cache=approval_cache,
        )

    resolved_callback = resolve_approval_callback(approval_policy)

    # Build attachment resolver
    if attachment_resolver is None:
        attachment_resolver = AttachmentResolver(
            base_path=project_root or Path.cwd(),
        )

    return AgentRuntime(
        agents=bundle.agents,
        attachment_resolver=attachment_resolver,
        toolset_specs=bundle.toolset_specs,
        toolset_registry=bundle.toolset_registry,
        approval_callback=resolved_callback,
        capability_rules=capability_rules or {"proc.exec.unlisted": "blocked"},
        capability_default=capability_default,
        return_permission_errors=return_permission_errors,
        max_depth=max_depth,
        on_event=on_event,
        message_log_callback=message_log_callback,
        verbosity=verbosity,
        project_root=project_root,
    )


async def run(
    worker_files: Sequence[str | Path],
    input_data: Any,
    *,
    python_files: Sequence[str | Path] | None = None,
    project_root: Path | None = None,
    model_override: str | None = None,
    approval_mode: Literal["prompt", "approve_all", "reject_all"] = "approve_all",
    approval_callback: ApprovalCallback | None = None,
    approval_cache: dict[Any, "ApprovalDecision"] | None = None,
    max_depth: int = 5,
    on_event: EventCallback | None = None,
    message_log_callback: Any | None = None,
    verbosity: int = 0,
    return_permission_errors: bool = False,
) -> tuple[Any, AgentRuntime]:
    """Load and run agents from worker files.

    This is the main entry point for running agents.

    Args:
        worker_files: Paths to .worker files
        input_data: Input data for the entry agent
        python_files: Optional Python files with custom toolsets
        project_root: Project root directory
        model_override: Override model for all agents
        approval_mode: Approval mode
        approval_callback: Custom approval callback
        approval_cache: Shared approval cache
        max_depth: Maximum delegation depth
        on_event: Event callback
        message_log_callback: Message logging callback
        verbosity: Verbosity level
        return_permission_errors: Return errors instead of raising

    Returns:
        Tuple of (output, runtime)
    """
    cwd = Path.cwd()
    project_root = project_root or cwd

    bundle = load_agents(
        worker_files,
        model_override=model_override,
        python_files=python_files,
        project_root=project_root,
        cwd=cwd,
    )

    approval_policy = RunApprovalPolicy(
        mode=approval_mode,
        approval_callback=approval_callback,
        cache=approval_cache,
        return_permission_errors=return_permission_errors,
    )

    runtime = build_runtime(
        bundle,
        project_root=project_root,
        approval_policy=approval_policy,
        max_depth=max_depth,
        on_event=on_event,
        message_log_callback=message_log_callback,
        verbosity=verbosity,
        return_permission_errors=return_permission_errors,
    )

    output = await run_entry_agent(bundle, input_data, runtime=runtime)
    return output, runtime


def run_sync(
    worker_files: Sequence[str | Path],
    input_data: Any,
    **kwargs: Any,
) -> tuple[Any, AgentRuntime]:
    """Synchronous wrapper for run().

    See run() for argument documentation.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "run_sync() cannot be called from a running event loop; "
            "use run() instead."
        )

    return asyncio.run(run(worker_files, input_data, **kwargs))
