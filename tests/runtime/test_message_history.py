"""Tests for message history behavior in runtime."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from llm_do.runtime import Worker, WorkerInput
from llm_do.ui.events import UIEvent
from tests.runtime.helpers import build_entry_context, build_runtime_context


def _count_user_prompts(messages: list[ModelMessage]) -> int:
    count = 0
    for msg in messages:
        for part in msg.parts:
            if isinstance(part, UserPromptPart):
                count += 1
    return count


def _make_prompt_count_model() -> FunctionModel:
    def respond(messages: list[ModelMessage], _: AgentInfo) -> ModelResponse:
        count = _count_user_prompts(messages)
        return ModelResponse(parts=[TextPart(content=f"user_prompts={count}")])

    async def stream_respond(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        response = respond(messages, info)
        text = "".join(
            part.content for part in response.parts if isinstance(part, TextPart)
        )
        yield text

    return FunctionModel(respond, stream_function=stream_respond)


@pytest.mark.anyio
async def test_entry_worker_receives_message_history_across_turns() -> None:
    """Entry worker (depth=0) should receive message_history on turn 2+."""
    events: list[UIEvent] = []

    worker = Worker(
        name="main",
        instructions="Count user prompts in message history.",
        model=_make_prompt_count_model(),
        toolsets=[],
    )
    ctx = build_entry_context(worker, on_event=events.append, verbosity=1)

    out1 = await ctx.run(worker, WorkerInput(input="turn 1"))
    assert out1 == "user_prompts=1"

    out2 = await ctx.run(worker, WorkerInput(input="turn 2"))
    assert out2 == "user_prompts=2"


@pytest.mark.anyio
async def test_nested_worker_call_does_not_inherit_conversation_history() -> None:
    """Nested worker calls should not receive the caller's message history."""
    events: list[UIEvent] = []

    sub_worker = Worker(
        name="sub",
        instructions="Count user prompts in message history.",
        model=_make_prompt_count_model(),
        toolsets=[],
    )

    # Simulate caller having prior conversation history.
    history: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart(content="previous turn")]),
        ModelResponse(parts=[TextPart(content="previous response")]),
    ]

    # Simulate a caller worker context (depth=1).
    caller_ctx = build_runtime_context(
        toolsets=[sub_worker],
        model="test-model",
        depth=1,
        messages=list(history),
        on_event=events.append,
        verbosity=1,
    )

    result = await caller_ctx.call("sub", WorkerInput(input="nested call"))
    assert result == "user_prompts=1"
