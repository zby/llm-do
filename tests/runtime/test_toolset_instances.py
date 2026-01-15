"""Tests for per-call toolset instantiation and cleanup."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset, ToolsetTool

from llm_do.runtime import Runtime, ToolsetSpec, Worker, WorkerArgs, WorkerInput, entry
from llm_do.runtime.approval import RunApprovalPolicy


@pytest.mark.anyio
async def test_recursive_worker_gets_fresh_toolset_instances() -> None:
    instance_ids: list[str] = []

    def build_stateful(_ctx):
        toolset = FunctionToolset()
        toolset_id = uuid4().hex
        toolset._instance_id = toolset_id
        instance_ids.append(toolset_id)

        @toolset.tool
        async def recurse(ctx: RunContext) -> str:
            if ctx.deps.depth <= 1:
                await ctx.deps.call("recursive", {"input": "nested"})
            return toolset._instance_id

        return toolset

    stateful_spec = ToolsetSpec(factory=build_stateful)
    worker = Worker(
        name="recursive",
        instructions="Call recurse tool.",
        model=TestModel(call_tools=["recurse"], custom_output_text="done"),
        toolset_specs=[stateful_spec],
    )
    worker.toolset_specs.append(worker.as_toolset_spec())

    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="approve_all"))
    await runtime.run_entry(worker, WorkerInput(input="go"))

    assert len(instance_ids) == 2
    assert instance_ids[0] != instance_ids[1]


@pytest.mark.anyio
async def test_worker_toolset_cleanup_runs_per_call() -> None:
    cleanup_calls: list[Any] = []

    class CleanupToolset(AbstractToolset[Any]):
        @property
        def id(self) -> str | None:
            return None

        async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool[Any]]:
            return {}

        async def call_tool(
            self,
            name: str,
            tool_args: dict[str, Any],
            ctx: Any,
            tool: ToolsetTool[Any],
        ) -> Any:
            raise ValueError("No tools registered")

        def cleanup(self) -> None:
            cleanup_calls.append(self)

    cleanup_spec = ToolsetSpec(factory=lambda _ctx: CleanupToolset())
    worker = Worker(
        name="cleanup_worker",
        instructions="Run cleanup toolset.",
        model=TestModel(custom_output_text="ok"),
        toolset_specs=[cleanup_spec],
    )

    runtime = Runtime()
    await runtime.run_entry(worker, WorkerInput(input="go"))
    await runtime.run_entry(worker, WorkerInput(input="again"))

    assert len(cleanup_calls) == 2


@pytest.mark.anyio
async def test_entry_function_toolset_cleanup_runs_per_call() -> None:
    cleanup_calls: list[Any] = []

    class CleanupToolset(AbstractToolset[Any]):
        @property
        def id(self) -> str | None:
            return None

        async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool[Any]]:
            return {}

        async def call_tool(
            self,
            name: str,
            tool_args: dict[str, Any],
            ctx: Any,
            tool: ToolsetTool[Any],
        ) -> Any:
            raise ValueError("No tools registered")

        def cleanup(self) -> None:
            cleanup_calls.append(self)

    cleanup_spec = ToolsetSpec(factory=lambda _ctx: CleanupToolset())

    @entry(toolsets=[cleanup_spec])
    async def main(_args: WorkerArgs, _runtime) -> str:
        return "ok"

    runtime = Runtime()
    await runtime.run_entry(main, WorkerInput(input="go"))
    await runtime.run_entry(main, WorkerInput(input="again"))

    assert len(cleanup_calls) == 2
