"""Execution boundary for runtime invocables."""
from __future__ import annotations

from typing import Any

from pydantic_ai.messages import ModelMessage

from ..ui.events import UserMessageEvent
from .approval import RunApprovalPolicy
from .context import WorkerRuntime
from .contracts import EventCallback, Invocable


async def run_invocable(
    invocable: Invocable,
    prompt: str,
    *,
    model: str | None = None,
    approval_policy: RunApprovalPolicy,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
    message_history: list[ModelMessage] | None = None,
) -> tuple[Any, WorkerRuntime]:
    """Run an invocable with the provided execution policy.

    RunApprovalPolicy gates tool calls during execution (LLM tool calls or
    programmatic ctx.deps.call), not the invocable invocation itself.
    """
    ctx: WorkerRuntime = WorkerRuntime.from_entry(
        invocable,
        model=model,
        run_approval_policy=approval_policy,
        messages=list(message_history) if message_history else None,
        on_event=on_event,
        verbosity=verbosity,
    )

    input_data: dict[str, str] = {"input": prompt}

    if on_event is not None:
        on_event(UserMessageEvent(worker=invocable.name, content=prompt))

    result: Any = await ctx.run(invocable, input_data)

    return result, ctx
