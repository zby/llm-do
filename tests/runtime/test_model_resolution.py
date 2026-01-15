from __future__ import annotations

from typing import Any, Optional

import pytest
from pydantic import BaseModel, TypeAdapter
from pydantic_ai.models import Model
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool

from llm_do.models import (
    LLM_DO_MODEL_ENV,
    ModelCompatibilityError,
    ModelConfigError,
    NoModelError,
)
from llm_do.runtime.worker import Worker
from tests.runtime.helpers import build_runtime_context


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
                args_validator=TypeAdapter(CaptureArgs).validator,
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
async def test_child_context_uses_parent_model() -> None:
    """Child context inherits model from parent when not overridden."""
    toolset = CaptureToolset()
    parent_model = TestModel(custom_output_text="parent")
    ctx = build_runtime_context(
        toolsets=[toolset],
        model=parent_model,
    )

    # Spawn child without model override - should inherit parent's model
    child = ctx.spawn_child(active_toolsets=[toolset])
    assert child.model is parent_model

    # Tool call should see the inherited model (resolved to same instance)
    await child.call("capture", {"value": 1})
    assert toolset.seen_model is parent_model


@pytest.mark.anyio
async def test_child_context_overrides_parent_model() -> None:
    """Child context can override parent's model."""
    toolset = CaptureToolset()
    parent_model = TestModel(custom_output_text="parent")
    child_model = TestModel(custom_output_text="child")
    ctx = build_runtime_context(
        toolsets=[toolset],
        model=parent_model,
    )

    # Spawn child with model override
    child = ctx.spawn_child(active_toolsets=[toolset], model=child_model)
    assert child.model is child_model

    # Tool call should see the overridden model
    await child.call("capture", {"value": 1})
    assert toolset.seen_model is child_model


@pytest.mark.anyio
async def test_string_model_resolved_to_model_instance() -> None:
    """String model is resolved to a concrete Model in RunContext."""
    toolset = CaptureToolset()
    ctx = build_runtime_context(
        toolsets=[toolset],
        model="test",  # String model name
    )

    # The context stores the string
    assert ctx.model == "test"

    # But when we call a tool, the RunContext should have a resolved Model
    await ctx.call("capture", {"value": 1})

    # The model in RunContext should be a TestModel instance (resolved from "test")
    assert toolset.seen_model is not None
    assert isinstance(toolset.seen_model, TestModel)


# --- construction-time model resolution tests ---


def test_worker_resolves_env_model_on_init(monkeypatch) -> None:
    monkeypatch.setenv(LLM_DO_MODEL_ENV, "test")
    worker = Worker(
        name="env-backed",
        instructions="Use env fallback.",
    )
    assert worker.model == "test"


def test_worker_missing_model_raises(monkeypatch) -> None:
    monkeypatch.delenv(LLM_DO_MODEL_ENV, raising=False)
    with pytest.raises(NoModelError, match="No model configured"):
        Worker(
            name="missing-model",
            instructions="Needs a model.",
        )


def test_worker_compatible_models_rejects_env(monkeypatch) -> None:
    monkeypatch.setenv(LLM_DO_MODEL_ENV, "openai:gpt-4o")
    with pytest.raises(ModelCompatibilityError, match="not compatible"):
        Worker(
            name="anthropic-only",
            instructions="Anthropic models only.",
            compatible_models=["anthropic:*"],
        )


def test_worker_model_and_compatible_models_raises() -> None:
    with pytest.raises(ModelConfigError, match="cannot have both"):
        Worker(
            name="strict",
            instructions="Be strict.",
            model="test",
            compatible_models=["test"],
        )


def test_worker_model_object_retained() -> None:
    model = TestModel(custom_output_text="Hello!")
    worker = Worker(
        name="object-model",
        instructions="Use model object.",
        model=model,
    )
    assert worker.model is model
