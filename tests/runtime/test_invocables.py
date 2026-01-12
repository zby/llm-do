"""Tests for invocable helpers."""

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from llm_do.runtime import Runtime, Worker, WorkerInput


def _prompt_echo_model() -> FunctionModel:
    def respond(messages: list[ModelMessage], _: AgentInfo) -> ModelResponse:
        for message in messages:
            for part in message.parts:
                if isinstance(part, UserPromptPart):
                    return ModelResponse(parts=[TextPart(content=part.content)])
        return ModelResponse(parts=[TextPart(content="")])

    return FunctionModel(respond)


async def _run_prompt(input_text: str) -> str:
    worker = Worker(
        name="main",
        instructions="Echo the prompt.",
        model=_prompt_echo_model(),
    )
    runtime = Runtime()
    result, _ctx = await runtime.run_invocable(worker, WorkerInput(input=input_text))
    return str(result)


@pytest.mark.anyio
async def test_empty_input_generates_non_empty_prompt() -> None:
    prompt = await _run_prompt("")
    assert prompt.strip() != ""


@pytest.mark.anyio
async def test_whitespace_input_generates_non_empty_prompt() -> None:
    prompt = await _run_prompt("   ")
    assert prompt.strip() != ""
