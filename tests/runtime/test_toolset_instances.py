"""Tests for per-call toolset instantiation and cleanup."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset, ToolsetTool

from llm_do.runtime import AgentSpec, EntrySpec, Runtime, ToolsetSpec, WorkerRuntime
from llm_do.runtime.approval import RunApprovalPolicy


@pytest.mark.anyio
async def test_recursive_agent_gets_fresh_toolset_instances() -> None:
    instance_ids: list[str] = []

    def build_stateful(_ctx):
        toolset = FunctionToolset()
        toolset_id = uuid4().hex
        toolset._instance_id = toolset_id
        instance_ids.append(toolset_id)

        @toolset.tool
        async def recurse(ctx: RunContext[WorkerRuntime]) -> str:
            deps = ctx.deps
            assert deps is not None
            if deps.frame.config.depth == 1:
                await deps.call_agent("recursive", {"input": "nested"})
            return toolset._instance_id

        return toolset

    stateful_spec = ToolsetSpec(factory=build_stateful)
    agent_spec = AgentSpec(
        name="recursive",
        instructions="Call recurse tool.",
        model=TestModel(call_tools=["recurse"], custom_output_text="done"),
        toolset_specs=[stateful_spec],
    )

    async def main(input_data, runtime: WorkerRuntime) -> str:
        return await runtime.call_agent(agent_spec, input_data)

    entry_spec = EntrySpec(name="entry", main=main)

    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="approve_all"))
    runtime.register_agents({agent_spec.name: agent_spec})
    await runtime.run_entry(entry_spec, {"input": "go"})

    assert len(instance_ids) == 2
    assert instance_ids[0] != instance_ids[1]


@pytest.mark.anyio
async def test_agent_toolset_cleanup_runs_per_call() -> None:
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
    agent_spec = AgentSpec(
        name="cleanup_agent",
        instructions="Run cleanup toolset.",
        model=TestModel(custom_output_text="ok"),
        toolset_specs=[cleanup_spec],
    )

    async def main(input_data, runtime: WorkerRuntime) -> str:
        return await runtime.call_agent(agent_spec, input_data)

    entry_spec = EntrySpec(name="entry", main=main)

    runtime = Runtime()
    runtime.register_agents({agent_spec.name: agent_spec})
    await runtime.run_entry(entry_spec, {"input": "go"})
    await runtime.run_entry(entry_spec, {"input": "again"})

    assert len(cleanup_calls) == 2

