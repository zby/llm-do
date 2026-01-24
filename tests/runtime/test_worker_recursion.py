import pytest
from pydantic_ai.models.test import TestModel

from llm_do.runtime import AgentEntry, EntryToolset, Runtime, build_entry
from llm_do.runtime.approval import RunApprovalPolicy


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

    entry = build_entry([str(worker_path)], [], project_root=tmp_path)

    assert isinstance(entry, AgentEntry)
    assert entry.toolset_specs
    ctx = entry.toolset_context
    assert ctx is not None
    toolset = entry.toolset_specs[0].factory(ctx)
    assert isinstance(toolset, EntryToolset)
    assert toolset.entry is entry


@pytest.mark.anyio
async def test_max_depth_blocks_self_recursion() -> None:
    entry_instance = AgentEntry(
        name="loop",
        instructions="Loop until depth is exceeded.",
        model=TestModel(call_tools=["loop"]),
    )
    entry_instance.toolset_specs = [entry_instance.as_toolset_spec()]
    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
        max_depth=2,
    )

    with pytest.raises(RuntimeError, match=r"Max depth exceeded calling 'loop': depth 2 >= max 2"):
        await runtime.run_entry(entry_instance, {"input": "go"})
