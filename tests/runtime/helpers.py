"""Helpers for building WorkerRuntime contexts in tests."""
from __future__ import annotations

from typing import Any

from pydantic_ai.toolsets import AbstractToolset

from llm_do.runtime import Runtime, WorkerArgs, WorkerRuntime
from llm_do.runtime.approval import RunApprovalPolicy
from llm_do.runtime.call import CallConfig, CallFrame
from llm_do.runtime.contracts import Entry, EventCallback, ModelType


def build_runtime_context(
    *,
    toolsets: list[AbstractToolset[Any]] | None = None,
    model: ModelType = "test",
    depth: int = 0,
    prompt: str = "",
    messages: list[Any] | None = None,
    run_approval_policy: RunApprovalPolicy | None = None,
    max_depth: int = 5,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
) -> WorkerRuntime:
    runtime = Runtime(
        run_approval_policy=run_approval_policy,
        max_depth=max_depth,
        on_event=on_event,
        verbosity=verbosity,
    )
    call_config = CallConfig(
        active_toolsets=tuple(toolsets or []),
        model=model,
        depth=depth,
    )
    frame = CallFrame(
        config=call_config,
        prompt=prompt,
        messages=list(messages) if messages else [],
    )
    return WorkerRuntime(runtime=runtime, frame=frame)


async def run_entry_test(
    entry: Entry,
    input_data: WorkerArgs,
    *,
    model: ModelType | None = None,
    run_approval_policy: RunApprovalPolicy | None = None,
    max_depth: int = 5,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
    message_history: list[Any] | None = None,
) -> tuple[Any, WorkerRuntime]:
    """Run an entry for testing, returning result and context.

    This is a convenience wrapper around Runtime.run_invocable() for tests
    that need both the result and the WorkerRuntime context.
    """
    runtime = Runtime(
        cli_model=model,
        run_approval_policy=run_approval_policy,
        max_depth=max_depth,
        on_event=on_event,
        verbosity=verbosity,
    )
    return await runtime.run_invocable(
        entry,
        input_data,
        model=model,
        message_history=message_history,
    )
