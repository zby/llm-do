"""Execution boundary for runtime entries."""
from __future__ import annotations

from typing import Any, cast

from ..ui.events import UserMessageEvent
from .approval import ApprovalPolicy, wrap_entry_for_approval
from .context import WorkerRuntime
from .contracts import EventCallback, Invocable
from .input_utils import coerce_worker_input
from .worker import Worker


async def run_entry(
    entry: Invocable,
    prompt: str,
    *,
    model: str | None = None,
    approval_policy: ApprovalPolicy,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
    message_history: list[Any] | None = None,
) -> tuple[Any, WorkerRuntime]:
    """Run a resolved entry with the provided execution policy.

    ApprovalPolicy gates tool calls during execution (LLM tool calls or
    programmatic ctx.deps.call), not the entry invocation itself.
    """
    wrapped_entry = wrap_entry_for_approval(entry, approval_policy)
    invocable_entry = cast(Invocable, wrapped_entry)

    ctx = WorkerRuntime.from_entry(
        invocable_entry,
        model=model,
        messages=list(message_history) if message_history else None,
        on_event=on_event,
        verbosity=verbosity,
    )

    if isinstance(invocable_entry, Worker):
        input_data = coerce_worker_input(invocable_entry.schema_in, prompt)
    else:
        input_data = {"input": prompt}

    if on_event is not None:
        on_event(UserMessageEvent(worker=getattr(invocable_entry, "name", "worker"), content=prompt))

    result = await ctx.run(invocable_entry, input_data)

    return result, ctx
