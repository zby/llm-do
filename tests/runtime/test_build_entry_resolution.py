from pathlib import Path

import pytest
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import AgentEntry, EntryToolset, ToolsetBuildContext, build_entry
from llm_do.toolsets.loader import instantiate_toolsets

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

    entry_instance = build_entry(
        worker_files,
        python_files,
        project_root=EXAMPLES_DIR / "web_research_agent",
    )
    assert isinstance(entry_instance, AgentEntry)

    entry_toolsets = instantiate_toolsets(
        entry_instance.toolset_specs,
        entry_instance.toolset_context or ToolsetBuildContext(worker_name=entry_instance.name),
    )
    extractor_toolset = next(
        toolset
        for toolset in entry_toolsets
        if isinstance(toolset, EntryToolset) and toolset.entry.name == "web_research_extractor"
    )
    extractor = extractor_toolset.entry
    extractor_toolsets = instantiate_toolsets(
        extractor.toolset_specs,
        extractor.toolset_context or ToolsetBuildContext(worker_name=extractor.name),
    )
    function_toolsets = [
        toolset for toolset in extractor_toolsets if isinstance(toolset, FunctionToolset)
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
from llm_do.runtime import ToolsetSpec, WorkerArgs, entry
from pydantic_ai.toolsets import FunctionToolset

_marker = {marker_literal}
with open(_marker, "a", encoding="utf-8") as handle:
    handle.write("x\\n")

def build_tools(_ctx):
    tools = FunctionToolset()

    @tools.tool
    def ping() -> str:
        return "pong"

    return tools

tools = ToolsetSpec(factory=build_tools)

@entry()
async def main(args: WorkerArgs, scope) -> str:
    return "ok"
"""
    )

    build_entry([], [str(module_path)], project_root=tmp_path)

    lines = marker_path.read_text(encoding="utf-8").splitlines()
    assert lines == ["x"]


@pytest.mark.anyio
async def test_build_entry_schema_in_ref_reuses_loaded_module(
    tmp_path: Path,
) -> None:
    marker_path = tmp_path / "marker.txt"
    schema_path = tmp_path / "schemas.py"
    marker_literal = repr(str(marker_path))
    schema_path.write_text(
        f"""\
from llm_do.runtime import PromptContent, WorkerArgs

_marker = {marker_literal}
with open(_marker, "a", encoding="utf-8") as handle:
    handle.write("x\\n")

class NoteInput(WorkerArgs):
    input: str

    def prompt_messages(self) -> list[PromptContent]:
        return [self.input]
""",
        encoding="utf-8",
    )
    worker_path = tmp_path / "main.worker"
    worker_path.write_text(
        """\
---
name: main
entry: true
schema_in_ref: schemas.py:NoteInput
---
Instructions.
""",
        encoding="utf-8",
    )

    build_entry([str(worker_path)], [str(schema_path)], project_root=tmp_path)

    lines = marker_path.read_text(encoding="utf-8").splitlines()
    assert lines == ["x"]


@pytest.mark.anyio
async def test_build_entry_resolves_schema_in_ref(tmp_path: Path) -> None:
    schema_path = tmp_path / "schemas.py"
    schema_path.write_text(
        """\
from llm_do.runtime import PromptContent, WorkerArgs


class NoteInput(WorkerArgs):
    input: str

    def prompt_messages(self) -> list[PromptContent]:
        return [self.input]
""",
        encoding="utf-8",
    )
    worker_path = tmp_path / "main.worker"
    worker_path.write_text(
        """\
---
name: main
entry: true
schema_in_ref: schemas.py:NoteInput
---
Instructions.
""",
        encoding="utf-8",
    )

    entry_instance = build_entry([str(worker_path)], [str(schema_path)], project_root=tmp_path)
    assert isinstance(entry_instance, AgentEntry)
    assert entry_instance.schema_in is not None
    assert entry_instance.schema_in.__name__ == "NoteInput"
