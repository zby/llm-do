"""Tests for per-call toolset instantiation and cleanup."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool

from llm_do.runtime import AgentEntry, Runtime, ToolsetSpec, WorkerArgs, entry
from llm_do.runtime.approval import RunApprovalPolicy


@pytest.mark.anyio
async def test_entry_calls_get_fresh_toolset_instances() -> None:
    instance_ids: list[str] = []

    class StatefulToolset(AbstractToolset[Any]):
        def __init__(self) -> None:
            self.instance_id = uuid4().hex
            instance_ids.append(self.instance_id)

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

    def build_stateful(_ctx):
        return StatefulToolset()

    stateful_spec = ToolsetSpec(factory=build_stateful)
    child = AgentEntry(
        name="child",
        instructions="Return output.",
        model=TestModel(custom_output_text="done"),
        toolset_specs=[stateful_spec],
    )

    @entry(toolsets=[child.as_toolset_spec()])
    async def main(_args: WorkerArgs, scope) -> str:
        await scope.call_tool("child", {"input": "one"})
        await scope.call_tool("child", {"input": "two"})
        return "ok"

    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="approve_all"))
    await runtime.run_entry(main, {"input": "go"})

    assert len(instance_ids) == 2
    assert instance_ids[0] != instance_ids[1]


@pytest.mark.anyio
async def test_entry_toolset_cleanup_runs_per_call() -> None:
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
    entry_instance = AgentEntry(
        name="cleanup_entry",
        instructions="Run cleanup toolset.",
        model=TestModel(custom_output_text="ok"),
        toolset_specs=[cleanup_spec],
    )

    runtime = Runtime()
    await runtime.run_entry(entry_instance, {"input": "go"})
    await runtime.run_entry(entry_instance, {"input": "again"})

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
    async def main(_args: WorkerArgs, _scope) -> str:
        return "ok"

    runtime = Runtime()
    await runtime.run_entry(main, {"input": "go"})
    await runtime.run_entry(main, {"input": "again"})

    assert len(cleanup_calls) == 2
