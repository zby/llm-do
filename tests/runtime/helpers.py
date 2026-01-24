"""Helpers for building CallRuntime contexts in tests."""
from __future__ import annotations

from typing import Any

from pydantic_ai.toolsets import AbstractToolset

from llm_do.runtime import CallRuntime, CallScope, Runtime, WorkerArgs
from llm_do.runtime.approval import RunApprovalPolicy
from llm_do.runtime.call import CallConfig, CallFrame
from llm_do.runtime.contracts import Entry, EventCallback, ModelType


def build_runtime_context(
    *,
    toolsets: list[AbstractToolset[Any]] | None = None,
    model: ModelType = "test",
    depth: int = 0,
    invocation_name: str = "test",
    prompt: str = "",
    messages: list[Any] | None = None,
    run_approval_policy: RunApprovalPolicy | None = None,
    max_depth: int = 5,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
) -> CallRuntime:
    runtime = Runtime(
        run_approval_policy=run_approval_policy,
        max_depth=max_depth,
        on_event=on_event,
        verbosity=verbosity,
    )
    call_config = CallConfig.build(
        toolsets or [],
        model=model,
        depth=depth,
        invocation_name=invocation_name,
    )
    frame = CallFrame(
        config=call_config,
        prompt=prompt,
        messages=list(messages) if messages else [],
    )
    return CallRuntime(runtime=runtime, frame=frame)


class _ScopeEntry:
    name = "test"
    toolset_specs: list[Any] = []
    schema_in = None

    def start(self, *_args: Any, **_kwargs: Any) -> CallScope:
        raise RuntimeError("Scope entry does not support start().")

    async def run_turn(self, _scope: CallScope, _input_data: Any) -> Any:
        raise RuntimeError("Scope entry does not support run_turn().")


def build_call_scope(
    *,
    toolsets: list[AbstractToolset[Any]] | None = None,
    model: ModelType = "test",
    depth: int = 0,
    invocation_name: str = "test",
    prompt: str = "",
    messages: list[Any] | None = None,
    run_approval_policy: RunApprovalPolicy | None = None,
    max_depth: int = 5,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
) -> CallScope:
    runtime = build_runtime_context(
        toolsets=toolsets,
        model=model,
        depth=depth,
        invocation_name=invocation_name,
        prompt=prompt,
        messages=messages,
        run_approval_policy=run_approval_policy,
        max_depth=max_depth,
        on_event=on_event,
        verbosity=verbosity,
    )
    entry = _ScopeEntry()
    return CallScope(entry=entry, runtime=runtime, toolsets=toolsets or [])


def build_call_scope_from_runtime(runtime: CallRuntime) -> CallScope:
    entry = _ScopeEntry()
    return CallScope(
        entry=entry,
        runtime=runtime,
        toolsets=list(runtime.frame.config.active_toolsets),
    )


async def run_entry_test(
    entry: Entry,
    input_data: WorkerArgs,
    *,
    run_approval_policy: RunApprovalPolicy | None = None,
    max_depth: int = 5,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
    message_history: list[Any] | None = None,
) -> tuple[Any, CallRuntime]:
    """Run an entry for testing, returning result and context.

    This is a convenience wrapper around Runtime.run_entry() for tests
    that need both the result and the CallRuntime context.
    """
    runtime = Runtime(
        run_approval_policy=run_approval_policy,
        max_depth=max_depth,
        on_event=on_event,
        verbosity=verbosity,
    )
    return await runtime.run_entry(
        entry,
        input_data,
        message_history=message_history,
    )
