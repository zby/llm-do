"""Tests for per-call toolset instantiation and cleanup."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset, ToolsetTool

from llm_do.runtime import AgentSpec, CallContext, FunctionEntry, Runtime
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
        async def recurse(ctx: RunContext[CallContext]) -> str:
            deps = ctx.deps
            assert deps is not None
            if deps.frame.config.depth == 1:
                await deps.call_agent("recursive", {"input": "nested"})
            return toolset._instance_id

        return toolset

    agent_spec = AgentSpec(
        name="recursive",
        instructions="Call recurse tool.",
        model=TestModel(call_tools=["recurse"], custom_output_text="done"),
        toolsets=[build_stateful],
    )

    async def main(input_data, runtime: CallContext) -> str:
        return await runtime.call_agent(agent_spec, input_data)

    entry = FunctionEntry(name="entry", fn=main)

    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="approve_all"))
    runtime.register_agents({agent_spec.name: agent_spec})
    await runtime.run_entry(entry, {"input": "go"})

    assert len(instance_ids) == 2
    assert instance_ids[0] != instance_ids[1]


@pytest.mark.anyio
async def test_agent_toolset_context_runs_per_call() -> None:
    enter_calls: list[Any] = []
    exit_calls: list[Any] = []

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

        async def __aenter__(self):
            enter_calls.append(self)
            return self

        async def __aexit__(self, *args: Any) -> None:
            exit_calls.append(self)

    def build_cleanup_toolset(_ctx):
        return CleanupToolset()
    agent_spec = AgentSpec(
        name="cleanup_agent",
        instructions="Run cleanup toolset.",
        model=TestModel(custom_output_text="ok"),
        toolsets=[build_cleanup_toolset],
    )

    async def main(input_data, runtime: CallContext) -> str:
        return await runtime.call_agent(agent_spec, input_data)

    entry = FunctionEntry(name="entry", fn=main)

    runtime = Runtime()
    runtime.register_agents({agent_spec.name: agent_spec})
    await runtime.run_entry(entry, {"input": "go"})
    await runtime.run_entry(entry, {"input": "again"})

    assert len(enter_calls) == 2
    assert len(exit_calls) == 2


@pytest.mark.anyio
async def test_invalid_toolset_factory_raises() -> None:
    def bad_factory(_ctx):
        return "not a toolset"

    agent_spec = AgentSpec(
        name="bad_toolset",
        instructions="Should fail.",
        model=TestModel(custom_output_text="ok"),
        toolsets=[bad_factory],
    )

    async def main(input_data, runtime: CallContext) -> str:
        return await runtime.call_agent(agent_spec, input_data)

    entry = FunctionEntry(name="entry", fn=main)

    runtime = Runtime()
    runtime.register_agents({agent_spec.name: agent_spec})

    with pytest.raises(TypeError, match="bad_factory"):
        await runtime.run_entry(entry, {"input": "go"})


@pytest.mark.anyio
async def test_shared_toolset_instance_reused_across_runs() -> None:
    seen: list[Any] = []

    class SharedToolset(AbstractToolset[Any]):
        @property
        def id(self) -> str | None:
            return None

        async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool[Any]]:
            seen.append(self)
            return {}

        async def call_tool(
            self,
            name: str,
            tool_args: dict[str, Any],
            ctx: Any,
            tool: ToolsetTool[Any],
        ) -> Any:
            raise ValueError("No tools registered")

    shared = SharedToolset()
    agent_spec = AgentSpec(
        name="shared_agent",
        instructions="No tools.",
        model=TestModel(custom_output_text="ok"),
        toolsets=[shared],
    )

    async def main(input_data, runtime: CallContext) -> str:
        return await runtime.call_agent(agent_spec, input_data)

    entry = FunctionEntry(name="entry", fn=main)

    runtime = Runtime()
    runtime.register_agents({agent_spec.name: agent_spec})
    await runtime.run_entry(entry, {"input": "go"})
    await runtime.run_entry(entry, {"input": "again"})

    assert seen
    assert {id(item) for item in seen} == {id(shared)}
