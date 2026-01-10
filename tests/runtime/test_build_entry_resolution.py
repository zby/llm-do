from pathlib import Path

import pytest
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import Worker, build_invocable_registry

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


@pytest.mark.anyio
async def test_build_entry_resolves_nested_worker_toolsets() -> None:
    worker_files = [
        str(EXAMPLES_DIR / "web_research_agent" / "main.worker"),
        str(EXAMPLES_DIR / "web_research_agent" / "web_research_extractor.worker"),
        str(EXAMPLES_DIR / "web_research_agent" / "web_research_consolidator.worker"),
        str(EXAMPLES_DIR / "web_research_agent" / "web_research_reporter.worker"),
    ]
    python_files = [str(EXAMPLES_DIR / "web_research_agent" / "tools.py")]

    registry = await build_invocable_registry(
        worker_files,
        python_files,
        entry_name="main",
        entry_model_override="test-model",
    )
    entry = registry.get("main")
    assert isinstance(entry, Worker)

    extractor = next(
        toolset
        for toolset in entry.toolsets
        if isinstance(toolset, Worker) and toolset.name == "web_research_extractor"
    )
    function_toolsets = [
        toolset for toolset in extractor.toolsets if isinstance(toolset, FunctionToolset)
    ]
    assert function_toolsets, "Expected extractor to include web_research_tools toolset"

    tool_names = {name for toolset in function_toolsets for name in toolset.tools}
    assert "fetch_page" in tool_names


@pytest.mark.anyio
async def test_build_entry_loads_python_modules_once(tmp_path: Path) -> None:
    marker_path = tmp_path / "marker.txt"
    module_path = tmp_path / "entry.py"
    marker_literal = repr(str(marker_path))

    module_path.write_text(
        f"""\
from llm_do.runtime import Worker
from pydantic_ai.toolsets import FunctionToolset

_marker = {marker_literal}
with open(_marker, "a", encoding="utf-8") as handle:
    handle.write("x\\n")

tools = FunctionToolset()

@tools.tool
def ping() -> str:
    return "pong"

main = Worker(name="main", instructions="hi", toolsets=[tools])
"""
    )

    await build_invocable_registry([], [str(module_path)], entry_name="main")

    lines = marker_path.read_text(encoding="utf-8").splitlines()
    assert lines == ["x"]


@pytest.mark.anyio
async def test_build_entry_resolves_schema_in_ref(tmp_path: Path) -> None:
    schema_path = tmp_path / "schemas.py"
    schema_path.write_text(
        """\
from llm_do.runtime import PromptSpec, WorkerArgs


class NoteInput(WorkerArgs):
    input: str

    def prompt_spec(self) -> PromptSpec:
        return PromptSpec(text=self.input)
""",
        encoding="utf-8",
    )
    worker_path = tmp_path / "main.worker"
    worker_path.write_text(
        """\
---
name: main
schema_in_ref: schemas.py:NoteInput
---
Instructions.
""",
        encoding="utf-8",
    )

    registry = await build_invocable_registry([str(worker_path)], [], entry_name="main")
    entry = registry.get("main")
    assert isinstance(entry, Worker)
    assert entry.schema_in is not None
    assert entry.schema_in.__name__ == "NoteInput"
