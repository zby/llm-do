from __future__ import annotations

import pytest
from pydantic_ai.toolsets import FunctionToolset

from tests.runtime.helpers import build_call_scope


@pytest.mark.anyio
async def test_call_scope_reuses_toolsets_and_cleans_up() -> None:
    cleanup_calls: list[FunctionToolset] = []

    class StatefulToolset(FunctionToolset):
        def __init__(self) -> None:
            super().__init__()
            self.counter = 0

        def cleanup(self) -> None:
            cleanup_calls.append(self)

    toolset = StatefulToolset()

    @toolset.tool
    def main() -> int:
        toolset.counter += 1
        return toolset.counter

    scope = build_call_scope(toolsets=[toolset], model="test")
    async with scope:
        await scope.call_tool("main", {})
        await scope.call_tool("main", {})
        assert toolset.counter == 2

    assert cleanup_calls == [toolset]
