from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset

from llm_do import register_model_factory
from llm_do.project import EntryConfig, build_registry, resolve_entry
from llm_do.project.host_toolsets import (
    build_agent_toolset_factory,
    build_host_toolsets,
)
from llm_do.toolsets.agent import AgentToolset
from tests.runtime.helpers import build_runtime_context, materialize_toolset_def

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


def _host_registry_kwargs(project_root: Path) -> dict[str, object]:
    return {
        "extra_toolsets": build_host_toolsets(Path.cwd(), project_root),
        "agent_toolset_factory": build_agent_toolset_factory(),
    }


def test_build_registry_records_model_id(tmp_path: Path) -> None:
    def factory(model_name: str) -> TestModel:
        return TestModel(custom_output_text=model_name)

    register_model_factory("custom_model_id_test", factory)

    agent_path = tmp_path / "main.agent"
    agent_path.write_text(
        """\
---
name: main
model: custom_model_id_test:demo
---
Hello
""",
        encoding="utf-8",
    )

    registry = build_registry(
        [str(agent_path)],
        [],
        project_root=tmp_path,
        **_host_registry_kwargs(tmp_path),
    )
    spec = registry.agents["main"]
    assert spec.model_id == "custom_model_id_test:demo"


@pytest.mark.anyio
async def test_build_registry_resolves_nested_agent_toolsets() -> None:
    agent_files = [
        str(EXAMPLES_DIR / "web_research_agent" / "main.agent"),
        str(EXAMPLES_DIR / "web_research_agent" / "web_research_extractor.agent"),
        str(EXAMPLES_DIR / "web_research_agent" / "web_research_consolidator.agent"),
        str(EXAMPLES_DIR / "web_research_agent" / "web_research_reporter.agent"),
    ]
    python_files = [str(EXAMPLES_DIR / "web_research_agent" / "tools.py")]

    registry = build_registry(
        agent_files,
        python_files,
        project_root=EXAMPLES_DIR / "web_research_agent",
        **_host_registry_kwargs(EXAMPLES_DIR / "web_research_agent"),
    )
    entry = resolve_entry(
        EntryConfig(agent="main"),
        registry,
        python_files=python_files,
        base_path=EXAMPLES_DIR / "web_research_agent",
    )

    entry_agent = registry.agents[entry.name]

    ctx = build_runtime_context(toolsets=[], model="test")
    entry_toolsets = [
        await materialize_toolset_def(toolset_def, ctx)
        for toolset_def in entry_agent.toolsets
    ]
    extractor_toolset = next(
        toolset
        for toolset in entry_toolsets
        if isinstance(toolset, AgentToolset)
        and toolset.spec.name == "web_research_extractor"
    )
    extractor = extractor_toolset.spec
    extractor_toolsets = [
        await materialize_toolset_def(toolset_def, ctx)
        for toolset_def in extractor.toolsets
    ]
    function_toolsets = [
        toolset
        for toolset in extractor_toolsets
        if isinstance(toolset, FunctionToolset)
    ]
    assert function_toolsets, "Expected extractor to include web_research_tools toolset"

    tool_names = {name for toolset in function_toolsets for name in toolset.tools}
    assert "fetch_page" in tool_names


@pytest.mark.anyio
async def test_build_registry_loads_python_modules_once(tmp_path: Path) -> None:
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

    registry = build_registry(
        [],
        [str(module_path)],
        project_root=tmp_path,
        **_host_registry_kwargs(tmp_path),
    )
    resolve_entry(
        EntryConfig(function=f"{module_path}:main"),
        registry,
        python_files=[module_path],
        base_path=tmp_path,
    )

    lines = marker_path.read_text(encoding="utf-8").splitlines()
    assert lines == ["x"]


@pytest.mark.anyio
async def test_build_registry_input_model_ref_reuses_loaded_module(
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
input_model_ref: schemas.py:NoteInput
---
Instructions.
""",
        encoding="utf-8",
    )

    registry = build_registry(
        [str(agent_path)],
        [str(schema_path)],
        project_root=tmp_path,
        **_host_registry_kwargs(tmp_path),
    )
    resolve_entry(
        EntryConfig(agent="main"),
        registry,
        python_files=[schema_path],
        base_path=tmp_path,
    )

    lines = marker_path.read_text(encoding="utf-8").splitlines()
    assert lines == ["x"]


@pytest.mark.anyio
async def test_build_registry_resolves_input_model_ref(tmp_path: Path) -> None:
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
input_model_ref: schemas.py:NoteInput
---
Instructions.
""",
        encoding="utf-8",
    )

    registry = build_registry(
        [str(agent_path)],
        [],
        project_root=tmp_path,
        **_host_registry_kwargs(tmp_path),
    )
    entry = resolve_entry(
        EntryConfig(agent="main"),
        registry,
        python_files=[],
        base_path=tmp_path,
    )
    assert entry.input_model is not None
    assert entry.input_model.__name__ == "NoteInput"


@pytest.mark.anyio
async def test_build_registry_rejects_duplicate_toolset_names(tmp_path: Path) -> None:
    reserved_worker = tmp_path / "shell_readonly.agent"
    reserved_worker.write_text(
        "---\nname: shell_readonly\n---\nReserved name.\n",
        encoding="utf-8",
    )
    entry_worker = tmp_path / "main.agent"
    entry_worker.write_text(
        "---\nname: main\n---\nHello.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate toolset name: shell_readonly"):
        build_registry(
            [str(reserved_worker), str(entry_worker)],
            [],
            project_root=tmp_path,
            **_host_registry_kwargs(tmp_path),
        )
