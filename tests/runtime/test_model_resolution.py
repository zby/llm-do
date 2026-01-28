from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from llm_do.models import LLM_DO_MODEL_ENV, NullModel
from llm_do.runtime import FunctionEntry, Runtime
from llm_do.runtime.call import CallConfig, CallFrame
from tests.runtime.helpers import build_runtime_context


@pytest.mark.anyio
async def test_child_context_passes_model_explicitly() -> None:
    """Child context uses the explicitly provided model."""
    parent_model = TestModel(custom_output_text="parent")
    ctx = build_runtime_context(
        toolsets=[],
        model=parent_model,
    )

    child = ctx.spawn_child(
        active_toolsets=[],
        model=parent_model,
        invocation_name="child",
    )
    assert child.frame.config.model is parent_model


@pytest.mark.anyio
async def test_child_context_overrides_parent_model() -> None:
    """Child context uses the explicitly provided override model."""
    parent_model = TestModel(custom_output_text="parent")
    child_model = TestModel(custom_output_text="child")
    ctx = build_runtime_context(
        toolsets=[],
        model=parent_model,
    )

    child = ctx.spawn_child(
        active_toolsets=[],
        model=child_model,
        invocation_name="child",
    )
    assert child.frame.config.model is child_model


def test_spawn_child_requires_args() -> None:
    """spawn_child requires explicit toolsets, model, and invocation name."""
    ctx = build_runtime_context(
        toolsets=[],
        model="test",
        invocation_name="parent",
    )
    with pytest.raises(TypeError):
        ctx.spawn_child(active_toolsets=[])  # type: ignore[call-arg]


def test_callframe_fork_requires_args() -> None:
    """CallFrame.fork requires explicit toolsets, model, and invocation name."""
    frame = CallFrame(
        config=CallConfig.build(
            [],
            model="test",
            depth=0,
            invocation_name="parent",
        ),
    )
    with pytest.raises(TypeError):
        frame.fork(active_toolsets=[])  # type: ignore[call-arg]


@pytest.mark.anyio
async def test_entry_uses_null_model(monkeypatch) -> None:
    """Entry functions use NullModel, ignoring LLM_DO_MODEL."""
    monkeypatch.setenv(LLM_DO_MODEL_ENV, "test")

    async def main(_input: Any, runtime: Any) -> str:
        assert isinstance(runtime.frame.config.model, NullModel)
        return "ok"

    entry = FunctionEntry(name="entry", fn=main)

    runtime = Runtime()
    result, _ctx = await runtime.run_entry(entry, {"input": "hi"})
    assert result == "ok"


@pytest.mark.anyio
async def test_entry_null_model_llm_call_raises() -> None:
    """Using NullModel for LLM calls should fail fast."""
    async def main(_input: Any, runtime: Any) -> str:
        agent = Agent(
            model=runtime.frame.config.model,
            instructions="test",
            deps_type=type(runtime),
        )
        await agent.run("hi", deps=runtime)
        return "ok"

    entry = FunctionEntry(name="entry", fn=main)

    runtime = Runtime()
    with pytest.raises(RuntimeError, match="NullModel cannot be used"):
        await runtime.run_entry(entry, {"input": "hi"})
