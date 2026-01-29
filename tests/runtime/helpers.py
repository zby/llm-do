"""Helpers for building CallContext contexts in tests."""
from __future__ import annotations

from typing import Any

from pydantic_ai.toolsets import AbstractToolset

from llm_do.models import ModelInput, resolve_model
from llm_do.runtime import (
    AgentRegistry,
    CallContext,
    CallScope,
    Entry,
    Runtime,
)
from llm_do.runtime.approval import RunApprovalPolicy, wrap_toolsets_for_approval
from llm_do.runtime.call import CallConfig, CallFrame
from llm_do.runtime.contracts import EventCallback


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
    call_config = CallConfig.build(
        toolsets or [],
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


def build_call_scope(
    *,
    toolsets: list[AbstractToolset[Any]],
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
    wrapped_toolsets = wrap_toolsets_for_approval(
        toolsets,
        runtime.config.approval_callback,
        return_permission_errors=runtime.config.return_permission_errors,
    )
    call_runtime = runtime.spawn_call_runtime(
        wrapped_toolsets,
        model=resolve_model(model),
        invocation_name=invocation_name,
        depth=depth,
    )
    return CallScope(runtime=call_runtime, toolsets=toolsets)


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
