"""Execution boundary for runtime invocables."""
from __future__ import annotations

from typing import Any

from pydantic_ai.messages import ModelMessage

from .approval import RunApprovalPolicy
from .contracts import EventCallback, Invocable
from .deps import WorkerRuntime
from .shared import Runtime


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
    runtime = Runtime(
        cli_model=model,
        run_approval_policy=approval_policy,
        on_event=on_event,
        verbosity=verbosity,
    )
    return await runtime.run_invocable(
        invocable,
        prompt,
        message_history=list(message_history) if message_history else None,
    )
