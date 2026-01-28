from pathlib import Path

import pytest
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import build_entry
from llm_do.toolsets.agent import AgentToolset
from llm_do.toolsets.loader import instantiate_toolsets

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


@pytest.mark.anyio
async def test_build_entry_resolves_nested_agent_toolsets() -> None:
    agent_files = [
        str(EXAMPLES_DIR / "web_research_agent" / "main.agent"),
        str(EXAMPLES_DIR / "web_research_agent" / "web_research_extractor.agent"),
        str(EXAMPLES_DIR / "web_research_agent" / "web_research_consolidator.agent"),
        str(EXAMPLES_DIR / "web_research_agent" / "web_research_reporter.agent"),
    ]
    python_files = [str(EXAMPLES_DIR / "web_research_agent" / "tools.py")]

    entry, registry = build_entry(
        agent_files,
        python_files,
        project_root=EXAMPLES_DIR / "web_research_agent",
    )

    entry_agent = registry.agents[entry.name]

    entry_toolsets = instantiate_toolsets(
        entry_agent.toolset_specs,
    )
    extractor_toolset = next(
        toolset
        for toolset in entry_toolsets
        if isinstance(toolset, AgentToolset) and toolset.spec.name == "web_research_extractor"
    )
    extractor = extractor_toolset.spec
    extractor_toolsets = instantiate_toolsets(
        extractor.toolset_specs,
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
from llm_do.runtime import FunctionEntry

_marker = {marker_literal}
with open(_marker, "a", encoding="utf-8") as handle:
    handle.write("x\\n")

async def main(_input, _runtime):
    return "ok"

ENTRY = FunctionEntry(
    name="main",
    fn=main,
)
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
from llm_do.runtime import PromptContent, AgentArgs

_marker = {marker_literal}
with open(_marker, "a", encoding="utf-8") as handle:
    handle.write("x\\n")

class NoteInput(AgentArgs):
    input: str

    def prompt_messages(self) -> list[PromptContent]:
        return [self.input]
""",
        encoding="utf-8",
    )
    agent_path = tmp_path / "main.agent"
    agent_path.write_text(
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

    build_entry([str(agent_path)], [str(schema_path)], project_root=tmp_path)

    lines = marker_path.read_text(encoding="utf-8").splitlines()
    assert lines == ["x"]


@pytest.mark.anyio
async def test_build_entry_resolves_schema_in_ref(tmp_path: Path) -> None:
    schema_path = tmp_path / "schemas.py"
    schema_path.write_text(
        """\
from llm_do.runtime import PromptContent, AgentArgs


class NoteInput(AgentArgs):
    input: str

    def prompt_messages(self) -> list[PromptContent]:
        return [self.input]
""",
        encoding="utf-8",
    )
    agent_path = tmp_path / "main.agent"
    agent_path.write_text(
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

    entry, _registry = build_entry([str(agent_path)], [], project_root=tmp_path)
    assert entry.schema_in is not None
    assert entry.schema_in.__name__ == "NoteInput"


@pytest.mark.anyio
async def test_build_entry_rejects_duplicate_toolset_names(tmp_path: Path) -> None:
    reserved_worker = tmp_path / "shell_readonly.agent"
    reserved_worker.write_text(
        "---\nname: shell_readonly\n---\nReserved name.\n",
        encoding="utf-8",
    )
    entry_worker = tmp_path / "main.agent"
    entry_worker.write_text(
        "---\nname: main\nentry: true\n---\nHello.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate toolset name: shell_readonly"):
        build_entry([str(reserved_worker), str(entry_worker)], [], project_root=tmp_path)
