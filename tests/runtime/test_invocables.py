"""Tests for invocable helpers."""

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from llm_do.runtime import AgentSpec, EntrySpec, Runtime


def _prompt_echo_model() -> FunctionModel:
    def respond(messages: list[ModelMessage], _: AgentInfo) -> ModelResponse:
        for message in messages:
            for part in message.parts:
                if isinstance(part, UserPromptPart):
                    content = part.content
                    if isinstance(content, str):
                        return ModelResponse(parts=[TextPart(content=content)])
                    text = " ".join(str(c) for c in content if isinstance(c, str))
                    return ModelResponse(parts=[TextPart(content=text)])
        return ModelResponse(parts=[TextPart(content="")])

    return FunctionModel(respond)


async def _run_prompt(input_text: str) -> str:
    agent_spec = AgentSpec(
        name="main",
        instructions="Echo the prompt.",
        model=_prompt_echo_model(),
    )

    async def main(input_data, runtime):
        return await runtime.call_agent(agent_spec, input_data)

    entry_spec = EntrySpec(name="main", main=main)

    runtime = Runtime()
    runtime.register_agents({agent_spec.name: agent_spec})
    result, _ctx = await runtime.run_entry(entry_spec, {"input": input_text})
    return str(result)


@pytest.mark.anyio
async def test_empty_input_generates_non_empty_prompt() -> None:
    prompt = await _run_prompt("")
    assert prompt.strip() != ""


@pytest.mark.anyio
async def test_whitespace_input_generates_non_empty_prompt() -> None:
    prompt = await _run_prompt("   ")
    assert prompt.strip() != ""
