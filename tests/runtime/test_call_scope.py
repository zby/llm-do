from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import Runtime, ToolsetSpec, Worker


@pytest.mark.anyio
async def test_call_scope_reuses_toolsets_and_cleans_up() -> None:
    cleanup_calls: list[FunctionToolset] = []
    build_calls: list[FunctionToolset] = []

    class StatefulToolset(FunctionToolset):
        def __init__(self) -> None:
            super().__init__()
            self.counter = 0

        def cleanup(self) -> None:
            cleanup_calls.append(self)

    def build_stateful(_ctx: object) -> FunctionToolset:
        toolset = StatefulToolset()
        build_calls.append(toolset)

        @toolset.tool
        def count() -> int:
            toolset.counter += 1
            return toolset.counter

        return toolset

    worker = Worker(
        name="counter",
        instructions="Call the count tool.",
        model=TestModel(call_tools=["count"], custom_output_text="ok"),
        toolset_specs=[ToolsetSpec(factory=build_stateful)],
    )
    runtime = Runtime()

    scope = worker.start(runtime)
    async with scope:
        await scope.run_turn({"input": "first"})
        await scope.run_turn({"input": "second"})
        assert len(build_calls) == 1

    assert cleanup_calls == build_calls
