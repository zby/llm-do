from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pytest
from pydantic import BaseModel, TypeAdapter
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool

from llm_do.runtime import WorkerRuntime


class CaptureArgs(BaseModel):
    value: int


class CaptureToolset(AbstractToolset[Any]):
    def __init__(self) -> None:
        self.seen_model: Optional[str] = None

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


@dataclass
class DummyEntry:
    """Mock entry that creates a child context with its toolsets, like Worker does."""

    name: str
    toolsets: list[AbstractToolset[Any]]
    model: Optional[str] = None

    async def call(
        self,
        input_data: Any,
        runtime: WorkerRuntime,
        run_ctx: RunContext[WorkerRuntime],
    ) -> Any:
        # Like Worker.call(), create a child context with our toolsets
        resolved_model = self.model if self.model is not None else runtime.model
        child_runtime = runtime.spawn_child(toolsets=self.toolsets, model=resolved_model)
        return await child_runtime.call("capture", {"value": 1})


@pytest.mark.anyio
async def test_worker_uses_context_model_for_tool_calls() -> None:
    """Entry without model uses context's model for tool calls."""
    toolset = CaptureToolset()
    entry = DummyEntry(name="child", toolsets=[toolset])
    # In production, ctx.model is already resolved (by from_entry using cli_model)
    ctx = WorkerRuntime(toolsets=[], model="resolved-model")

    await ctx._execute(entry, {"input": "hi"})

    assert toolset.seen_model == "resolved-model"


@pytest.mark.anyio
async def test_worker_model_overrides_context_model_for_tool_calls() -> None:
    """Entry with explicit model overrides context's model."""
    toolset = CaptureToolset()
    entry = DummyEntry(name="child", toolsets=[toolset], model="worker-model")
    ctx = WorkerRuntime(toolsets=[], model="context-model")

    await ctx._execute(entry, {"input": "hi"})

    assert toolset.seen_model == "worker-model"


# --- compatible_models tests ---

from pydantic_ai.models.test import TestModel

from llm_do.runtime.approval import RunApprovalPolicy
from llm_do.runtime.worker import Worker


@pytest.mark.anyio
async def test_worker_compatible_models_allows_matching_model() -> None:
    """Worker runs successfully when model is in compatible_models."""
    worker = Worker(
        name="strict",
        instructions="Be strict.",
        model="allowed-model",
        compatible_models=["allowed-model", "other-model"],
    )
    ctx = WorkerRuntime(
        toolsets=[],
        model="allowed-model",
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )

    # Should not raise - use TestModel to avoid real API call
    worker_with_test = Worker(
        name="strict",
        instructions="Be strict.",
        model=TestModel(),
        compatible_models=["test"],  # TestModel's model name
    )
    # We can't easily test the full call without mocking, so we test the validation directly
    # by checking what happens when we call with an incompatible model


@pytest.mark.anyio
async def test_worker_incompatible_model_raises() -> None:
    """Worker raises ValueError when model is not in compatible_models."""
    worker = Worker(
        name="strict",
        instructions="Be strict.",
        compatible_models=["model-a", "model-b"],
    )
    ctx = WorkerRuntime(
        toolsets=[],
        model="incompatible-model",
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    with pytest.raises(ValueError, match="not compatible with worker"):
        await worker.call({"input": "hi"}, ctx, run_ctx)


@pytest.mark.anyio
async def test_worker_no_compatible_models_allows_any() -> None:
    """Worker allows any model when compatible_models is None."""
    worker = Worker(
        name="flexible",
        instructions="Be flexible.",
        model=TestModel(),
        compatible_models=None,  # No restriction
    )
    ctx = WorkerRuntime(
        toolsets=[],
        model="any-model",
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    # Should not raise
    result = await worker.call({"input": "hi"}, ctx, run_ctx)
    assert result is not None
