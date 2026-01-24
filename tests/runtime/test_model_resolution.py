from __future__ import annotations

from typing import Any, Optional, cast

import pytest
from pydantic import BaseModel, TypeAdapter
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_core import SchemaValidator

from llm_do.models import LLM_DO_MODEL_ENV, NullModel
from llm_do.runtime import CallScope, EntrySpec, Runtime
from llm_do.runtime.call import CallConfig, CallFrame
from tests.runtime.helpers import build_call_scope, build_runtime_context


class CaptureArgs(BaseModel):
    value: int


class CaptureToolset(AbstractToolset[Any]):
    def __init__(self) -> None:
        self.seen_model: Optional[Model] = None

    @property
    def id(self) -> str | None:
        return "capture"

    async def get_tools(self, run_ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        tool_def = ToolDefinition(
            name="capture",
            description="Capture run context model.",
            parameters_json_schema=CaptureArgs.model_json_schema(),
        )
        return {
            "capture": ToolsetTool(
                toolset=self,
                tool_def=tool_def,
                max_retries=0,
                args_validator=cast(SchemaValidator, TypeAdapter(CaptureArgs).validator),
            )
        }

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        run_ctx: RunContext[Any],
        tool: ToolsetTool[Any],
    ) -> Any:
        self.seen_model = run_ctx.model
        return run_ctx.model


@pytest.mark.anyio
async def test_child_context_passes_model_explicitly() -> None:
    """Child context uses the explicitly provided model."""
    toolset = CaptureToolset()
    parent_model = TestModel(custom_output_text="parent")
    ctx = build_runtime_context(
        toolsets=[toolset],
        model=parent_model,
    )

    child = ctx.spawn_child(
        active_toolsets=[toolset],
        model=parent_model,
        invocation_name="child",
    )
    assert child.frame.config.model is parent_model

    scope = CallScope(runtime=child, toolsets=[toolset])
    async with scope:
        await scope.call_tool("capture", {"value": 1})
    assert toolset.seen_model is parent_model


@pytest.mark.anyio
async def test_child_context_overrides_parent_model() -> None:
    """Child context uses the explicitly provided override model."""
    toolset = CaptureToolset()
    parent_model = TestModel(custom_output_text="parent")
    child_model = TestModel(custom_output_text="child")
    ctx = build_runtime_context(
        toolsets=[toolset],
        model=parent_model,
    )

    child = ctx.spawn_child(
        active_toolsets=[toolset],
        model=child_model,
        invocation_name="child",
    )
    assert child.frame.config.model is child_model

    scope = CallScope(runtime=child, toolsets=[toolset])
    async with scope:
        await scope.call_tool("capture", {"value": 1})
    assert toolset.seen_model is child_model


def test_spawn_child_requires_args() -> None:
    """spawn_child requires explicit toolsets, model, and invocation name."""
    toolset = CaptureToolset()
    ctx = build_runtime_context(
        toolsets=[toolset],
        model="test",
        invocation_name="parent",
    )
    with pytest.raises(TypeError):
        ctx.spawn_child(active_toolsets=[toolset])  # type: ignore[call-arg]


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
async def test_string_model_resolved_to_model_instance() -> None:
    """String model is resolved to a concrete Model in RunContext."""
    toolset = CaptureToolset()
    scope = build_call_scope(
        toolsets=[toolset],
        model="test",
    )

    async with scope:
        await scope.call_tool("capture", {"value": 1})

    assert toolset.seen_model is not None
    assert isinstance(toolset.seen_model, TestModel)


@pytest.mark.anyio
async def test_entry_uses_null_model(monkeypatch) -> None:
    """Entry functions use NullModel, ignoring LLM_DO_MODEL."""
    monkeypatch.setenv(LLM_DO_MODEL_ENV, "test")

    async def main(_input: Any, runtime: Any) -> str:
        assert isinstance(runtime.frame.config.model, NullModel)
        return "ok"

    entry_spec = EntrySpec(name="entry", main=main)

    runtime = Runtime()
    result, _ctx = await runtime.run_entry(entry_spec, {"input": "hi"})
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

    entry_spec = EntrySpec(name="entry", main=main)

    runtime = Runtime()
    with pytest.raises(RuntimeError, match="NullModel cannot be used"):
        await runtime.run_entry(entry_spec, {"input": "hi"})
