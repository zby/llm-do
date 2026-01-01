"""Tests for invocable helpers."""

from llm_do.runtime.worker import _build_user_prompt


def test_build_user_prompt_handles_empty_input() -> None:
    prompt = _build_user_prompt("")
    assert isinstance(prompt, str)
    assert prompt.strip() != ""


def test_build_user_prompt_handles_empty_input_dict() -> None:
    prompt = _build_user_prompt({"input": ""})
    assert isinstance(prompt, str)
    assert prompt.strip() != ""
