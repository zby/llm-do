"""Tests for per-worker toolset instantiation and cleanup."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from llm_do.runtime import Runtime, WorkerInput, build_entry
from llm_do.runtime.worker import WorkerToolset


def _find_loaded_module(path: Path):
    resolved = str(path.resolve())
    for module in sys.modules.values():
        if getattr(module, "__file__", None) == resolved:
            return module
    raise AssertionError(f"Module for {resolved} not found in sys.modules")


@pytest.mark.anyio
async def test_per_worker_toolset_instances_isolated_handles(tmp_path: Path) -> None:
    tools_path = tmp_path / "tools.py"
    tools_path.write_text(
        """\
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import ToolsetSpec

def build_stateful(_ctx):
    tools = FunctionToolset()
    tools._handles = {}
    return tools

stateful_tools = ToolsetSpec(factory=build_stateful)
""",
        encoding="utf-8",
    )
    worker_a_path = tmp_path / "worker_a.worker"
    worker_a_path.write_text(
        """\
---
name: worker_a
entry: true
toolsets:
  - stateful_tools
  - worker_b
---
Worker A.
""",
        encoding="utf-8",
    )
    worker_b_path = tmp_path / "worker_b.worker"
    worker_b_path.write_text(
        """\
---
name: worker_b
toolsets:
  - stateful_tools
---
Worker B.
""",
        encoding="utf-8",
    )

    entry = build_entry(
        [str(worker_a_path), str(worker_b_path)],
        [str(tools_path)],
    )

    toolset_a = next(toolset for toolset in entry.toolsets if hasattr(toolset, "_handles"))
    worker_b_toolset = next(
        toolset
        for toolset in entry.toolsets
        if isinstance(toolset, WorkerToolset) and toolset.worker.name == "worker_b"
    )
    toolset_b = next(
        toolset for toolset in worker_b_toolset.worker.toolsets if hasattr(toolset, "_handles")
    )

    assert toolset_a is not toolset_b
    toolset_a._handles["handle_a"] = True
    assert "handle_a" not in toolset_b._handles


@pytest.mark.anyio
async def test_cleanup_called_on_run_end(tmp_path: Path) -> None:
    tools_path = tmp_path / "tools.py"
    tools_path.write_text(
        """\
from typing import Any

from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from llm_do.runtime import ToolsetSpec, WorkerArgs, WorkerRuntime, entry

CLEANUP_CALLS = []

class CleanupToolset(AbstractToolset[Any]):
    @property
    def id(self) -> str | None:
        return None

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool[Any]]:
        return {}

    async def call_tool(self, name: str, tool_args: dict[str, Any], ctx: Any, tool: ToolsetTool[Any]) -> Any:
        raise ValueError("No tools registered")

    def cleanup(self) -> None:
        CLEANUP_CALLS.append(self)

def build_cleanup(_ctx):
    return CleanupToolset()

cleanup_tools = ToolsetSpec(factory=build_cleanup)

@entry(toolsets=["cleanup_tools"])
async def main(args: WorkerArgs, runtime: WorkerRuntime) -> str:
    return "ok"
""",
        encoding="utf-8",
    )
    worker_path = tmp_path / "worker.worker"
    worker_path.write_text(
        """\
---
name: worker
toolsets:
  - cleanup_tools
---
Worker.
""",
        encoding="utf-8",
    )

    entry = build_entry([str(worker_path)], [str(tools_path)])
    runtime = Runtime(cli_model="test")

    result, _ctx = await runtime.run_entry(entry, WorkerInput(input="go"))
    assert result == "ok"

    module = _find_loaded_module(tools_path)
    cleanup_calls = module.CLEANUP_CALLS
    assert len(cleanup_calls) == 2
