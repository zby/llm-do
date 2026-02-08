"""Helpers for building CallContext contexts in tests."""
from __future__ import annotations

import inspect
from typing import Any

from pydantic_ai._run_context import RunContext
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.toolsets._dynamic import DynamicToolset
from pydantic_ai.usage import RunUsage

from llm_do.models import ModelInput, resolve_model
from llm_do.project import AgentRegistry
from llm_do.runtime import (
    CallContext,
    CallScope,
    Entry,
    Runtime,
)
from llm_do.runtime.approval import RunApprovalPolicy
from llm_do.runtime.call import CallConfig, CallFrame
from llm_do.runtime.contracts import EventCallback
from llm_do.runtime.tooling import ToolDef, ToolsetDef


def build_runtime_context(
    *,
    toolsets: list[AbstractToolset[Any]] | None = None,
    model: ModelInput = "test",
    depth: int = 0,
    invocation_name: str = "test",
    prompt: str = "",
    messages: list[Any] | None = None,
    run_approval_policy: RunApprovalPolicy | None = None,
    max_depth: int = 5,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
) -> CallContext:
    runtime = Runtime(
        run_approval_policy=run_approval_policy,
        max_depth=max_depth,
        on_event=on_event,
        verbosity=verbosity,
    )
    resolved_model = resolve_model(model)
    call_config = CallConfig(
        active_toolsets=tuple(toolsets or []),
        model=resolved_model,
        depth=depth,
        invocation_name=invocation_name,
    )
    frame = CallFrame(
        config=call_config,
        prompt=prompt,
        messages=list(messages) if messages else [],
    )
    return CallContext(runtime=runtime, frame=frame)


def build_run_context(ctx: CallContext) -> RunContext:
    return RunContext(
        deps=ctx,
        model=ctx.frame.config.model,
        usage=RunUsage(),
        prompt=ctx.frame.prompt,
        messages=list(ctx.frame.messages),
        run_step=0,
        retry=0,
    )


async def materialize_toolset_def(
    toolset_def: ToolsetDef, ctx: CallContext
) -> AbstractToolset[Any] | None:
    run_ctx = build_run_context(ctx)
    if isinstance(toolset_def, DynamicToolset):
        toolset = toolset_def.toolset_func(run_ctx)
        if inspect.isawaitable(toolset):
            toolset = await toolset
        return toolset
    if isinstance(toolset_def, AbstractToolset):
        return toolset_def
    toolset = toolset_def(run_ctx)  # type: ignore[call-arg]
    if inspect.isawaitable(toolset):
        toolset = await toolset
    return toolset


def build_call_scope(
    *,
    toolsets: list[AbstractToolset[Any]],
    tools: list[ToolDef] | None = None,
    model: ModelInput = "test",
    depth: int = 0,
    invocation_name: str = "test",
    run_approval_policy: RunApprovalPolicy | None = None,
    max_depth: int = 5,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
) -> CallScope:
    runtime = Runtime(
        run_approval_policy=run_approval_policy,
        max_depth=max_depth,
        on_event=on_event,
        verbosity=verbosity,
    )
    call_runtime = runtime.spawn_call_runtime(
        toolsets,
        model=resolve_model(model),
        invocation_name=invocation_name,
        depth=depth,
    )
    return CallScope(runtime=call_runtime, toolsets=toolsets, tools=tools or [])


async def run_entry_test(
    entry: Entry,
    input_data: Any,
    *,
    run_approval_policy: RunApprovalPolicy | None = None,
    max_depth: int = 5,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
    message_history: list[Any] | None = None,
    agent_registry: AgentRegistry | None = None,
) -> tuple[Any, CallContext]:
    """Run an entry for testing, returning result and context.

    This is a convenience wrapper around Runtime.run_entry() for tests
    that need both the result and the CallContext context.
    """
    runtime = Runtime(
        run_approval_policy=run_approval_policy,
        max_depth=max_depth,
        on_event=on_event,
        verbosity=verbosity,
    )
    if agent_registry is not None:
        runtime.register_registry(agent_registry)
    return await runtime.run_entry(
        entry,
        input_data,
        message_history=message_history,
    )
