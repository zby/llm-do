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

from llm_do.runtime import AgentSpec, FunctionEntry, Runtime
from tests.runtime.helpers import build_runtime_context


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
async def test_entry_agent_does_not_receive_message_history_across_turns() -> None:
    """Entry agent ignores message_history until runtime owns sync."""

    agent_spec = AgentSpec(
        name="main",
        instructions="Count user prompts in message history.",
        model=_make_prompt_count_model(),
    )

    async def main(input_data, runtime) -> str:
        return await runtime.call_agent(agent_spec, input_data)

    entry = FunctionEntry(name="main", fn=main)

    runtime = Runtime(verbosity=1)
    runtime.register_agents({agent_spec.name: agent_spec})

    out1, ctx1 = await runtime.run_entry(entry, {"input": "turn 1"})
    assert out1 == "user_prompts=1"

    out2, _ctx2 = await runtime.run_entry(
        entry,
        {"input": "turn 2"},
        message_history=ctx1.frame.messages,
    )
    assert out2 == "user_prompts=1"


@pytest.mark.anyio
async def test_nested_agent_call_does_not_inherit_conversation_history() -> None:
    """Nested agent calls should not receive the caller's message history."""
    agent_spec = AgentSpec(
        name="sub",
        instructions="Count user prompts in message history.",
        model=_make_prompt_count_model(),
    )

    history: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart(content="previous turn")]),
        ModelResponse(parts=[TextPart(content="previous response")]),
    ]

    caller_ctx = build_runtime_context(
        toolsets=[],
        model="test",
        depth=1,
        messages=list(history),
        verbosity=1,
    )

    result = await caller_ctx.call_agent(agent_spec, {"input": "nested call"})
    assert result == "user_prompts=1"
