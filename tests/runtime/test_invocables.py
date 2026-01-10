"""Tests for invocable helpers."""

from llm_do.runtime import PromptSpec, WorkerInput
from llm_do.runtime.worker import _build_user_prompt


def test_build_user_prompt_handles_empty_input() -> None:
    prompt = _build_user_prompt(PromptSpec(text=""))
    assert isinstance(prompt, str)
    assert prompt.strip() != ""


def test_build_user_prompt_handles_empty_input_args() -> None:
    prompt = _build_user_prompt(WorkerInput(input="").prompt_spec())
    assert isinstance(prompt, str)
    assert prompt.strip() != ""
