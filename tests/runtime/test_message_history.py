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

from llm_do.runtime import AgentEntry, Runtime, ToolsetBuildContext
from llm_do.runtime.events import RuntimeEvent
from tests.runtime.helpers import build_call_scope


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
async def test_entry_receives_message_history_across_turns() -> None:
    """Entry (depth=0) should receive message_history on turn 2+."""
    events: list[RuntimeEvent] = []

    entry_instance = AgentEntry(
        name="main",
        instructions="Count user prompts in message history.",
        model=_make_prompt_count_model(),
    )
    runtime = Runtime(on_event=events.append, verbosity=1)

    out1, ctx1 = await runtime.run_entry(entry_instance, {"input": "turn 1"})
    assert out1 == "user_prompts=1"

    out2, ctx2 = await runtime.run_entry(
        entry_instance,
        {"input": "turn 2"},
        message_history=ctx1.frame.messages,
    )
    assert out2 == "user_prompts=2"


@pytest.mark.anyio
async def test_nested_entry_call_does_not_inherit_conversation_history() -> None:
    """Nested entry calls should not receive the caller's message history."""
    events: list[RuntimeEvent] = []

    sub_entry = AgentEntry(
        name="sub",
        instructions="Count user prompts in message history.",
        model=_make_prompt_count_model(),
    )

    history: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart(content="previous turn")]),
        ModelResponse(parts=[TextPart(content="previous response")]),
    ]

    sub_toolset = sub_entry.as_toolset_spec().factory(
        ToolsetBuildContext(worker_name="caller")
    )
    caller_scope = build_call_scope(
        toolsets=[sub_toolset],
        model="test",
        depth=0,
        messages=list(history),
        on_event=events.append,
        verbosity=1,
    )

    result = await caller_scope.call_tool("sub", {"input": "nested call"})
    assert result == "user_prompts=1"
