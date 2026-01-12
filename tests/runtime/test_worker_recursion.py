import pytest
from pydantic_ai.models.test import TestModel

from llm_do.runtime import Runtime, WorkerInput, build_entry
from llm_do.runtime.approval import RunApprovalPolicy
from llm_do.runtime.worker import Worker, WorkerToolset


@pytest.mark.anyio
async def test_registry_allows_self_toolset_reference(tmp_path) -> None:
    worker_path = tmp_path / "recursive.worker"
    worker_path.write_text(
        """---
name: recursive
entry: true
model: test
toolsets:
  - recursive
---
Call yourself.
"""
    )

    entry = build_entry([str(worker_path)], [])

    assert isinstance(entry, Worker)
    assert entry.toolsets
    # Toolset resolution wraps Workers in WorkerToolset adapters
    assert isinstance(entry.toolsets[0], WorkerToolset)
    assert entry.toolsets[0].worker is entry


@pytest.mark.anyio
async def test_max_depth_blocks_self_recursion() -> None:
    worker = Worker(
        name="loop",
        instructions="Loop until depth is exceeded.",
        model=TestModel(call_tools=["loop"]),
    )
    # Use as_toolset() for explicit Worker-as-tool exposure
    worker.toolsets = [worker.as_toolset()]
    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
        max_depth=2,
    )

    with pytest.raises(RuntimeError, match="Max depth exceeded: 2"):
        await runtime.run_invocable(worker, WorkerInput(input="go"))
