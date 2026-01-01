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

    async def get_tools(self, ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
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
        ctx: RunContext[Any],
        tool: ToolsetTool[Any],
    ) -> Any:
        self.seen_model = ctx.model
        return ctx.model


@dataclass
class DummyEntry:
    name: str
    toolsets: list[AbstractToolset[Any]]
    model: Optional[str] = None
    kind: str = "worker"

    async def call(
        self,
        input_data: Any,
        ctx: WorkerRuntime,
        run_ctx: RunContext[WorkerRuntime],
    ) -> Any:
        return await ctx.call("capture", {"value": 1})


@pytest.mark.anyio
async def test_worker_uses_cli_model_for_tool_calls() -> None:
    toolset = CaptureToolset()
    entry = DummyEntry(name="child", toolsets=[toolset])
    ctx = WorkerRuntime(toolsets=[], model="parent-model", cli_model="cli-model")

    await ctx._execute(entry, {"input": "hi"})

    assert toolset.seen_model == "cli-model"


@pytest.mark.anyio
async def test_worker_model_overrides_cli_model_for_tool_calls() -> None:
    toolset = CaptureToolset()
    entry = DummyEntry(name="child", toolsets=[toolset], model="worker-model")
    ctx = WorkerRuntime(toolsets=[], model="parent-model", cli_model="cli-model")

    await ctx._execute(entry, {"input": "hi"})

    assert toolset.seen_model == "worker-model"
