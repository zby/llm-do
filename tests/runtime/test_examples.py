"""Smoke tests for representative examples/ patterns."""
from pathlib import Path

import pytest

from llm_do.runtime import (
    build_entry,
    load_toolsets_from_files,
    load_agent_file,
)
from llm_do.toolsets.agent import AgentToolset
from llm_do.toolsets.loader import instantiate_toolsets

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


@pytest.mark.anyio
async def test_single_worker_example_builds():
    worker_file = load_agent_file(EXAMPLES_DIR / "calculator" / "main.agent")
    assert "calc_tools" in worker_file.toolsets

    toolsets = load_toolsets_from_files([EXAMPLES_DIR / "calculator" / "tools.py"])
    assert "calc_tools" in toolsets

    project_root = EXAMPLES_DIR / "calculator"
    entry_spec, registry = build_entry(
        [str(project_root / "main.agent")],
        [str(project_root / "tools.py")],
        project_root=project_root,
    )
    agent = registry.agents[entry_spec.name]
    assert len(agent.toolset_specs) == 1


@pytest.mark.anyio
async def test_delegation_example_builds():
    project_root = EXAMPLES_DIR / "pitchdeck_eval"
    entry_spec, registry = build_entry(
        [
            str(project_root / "main.agent"),
            str(project_root / "pitch_evaluator.agent"),
        ],
        [],
        project_root=project_root,
    )
    agent = registry.agents[entry_spec.name]
    toolsets = instantiate_toolsets(
        agent.toolset_specs,
    )
    toolset_names = [
        toolset.spec.name for toolset in toolsets if isinstance(toolset, AgentToolset)
    ]
    assert "pitch_evaluator" in toolset_names


@pytest.mark.anyio
async def test_code_entry_example_builds():
    project_root = EXAMPLES_DIR / "pitchdeck_eval_code_entry"
    entry_spec, _registry = build_entry(
        [str(project_root / "pitch_evaluator.agent")],
        [str(project_root / "tools.py")],
        project_root=project_root,
    )
    assert entry_spec.name


@pytest.mark.anyio
async def test_server_side_tools_example_builds():
    worker_file = load_agent_file(EXAMPLES_DIR / "web_searcher" / "main.agent")
    assert len(worker_file.server_side_tools) == 1
    assert worker_file.server_side_tools[0]["tool_type"] == "web_search"

    project_root = EXAMPLES_DIR / "web_searcher"
    entry_spec, registry = build_entry(
        [str(project_root / "main.agent")],
        [],
        project_root=project_root,
    )
    agent = registry.agents[entry_spec.name]
    assert len(agent.builtin_tools) == 1


@pytest.mark.anyio
async def test_file_organizer_example_builds():
    """Test file_organizer: stabilizing pattern with semantic/mechanical separation."""
    worker_file = load_agent_file(EXAMPLES_DIR / "file_organizer" / "main.agent")
    assert "file_tools" in worker_file.toolsets
    assert "shell_file_ops" in worker_file.toolsets

    toolsets = load_toolsets_from_files([EXAMPLES_DIR / "file_organizer" / "tools.py"])
    assert "file_tools" in toolsets

    project_root = EXAMPLES_DIR / "file_organizer"
    entry_spec, registry = build_entry(
        [str(project_root / "main.agent")],
        [str(project_root / "tools.py")],
        project_root=project_root,
    )
    agent = registry.agents[entry_spec.name]
    assert len(agent.toolset_specs) == 2  # file_tools + shell_file_ops


@pytest.mark.anyio
async def test_recursive_summarizer_example_builds():
    worker_file = load_agent_file(EXAMPLES_DIR / "recursive_summarizer" / "main.agent")
    assert "filesystem_project" in worker_file.toolsets
    assert "summarizer" in worker_file.toolsets

    project_root = EXAMPLES_DIR / "recursive_summarizer"
    entry_spec, registry = build_entry(
        [
            str(project_root / "main.agent"),
            str(project_root / "summarizer.agent"),
        ],
        [],
        project_root=project_root,
    )
    agent = registry.agents[entry_spec.name]
    toolsets = instantiate_toolsets(
        agent.toolset_specs,
    )
    toolset_names = [
        toolset.spec.name for toolset in toolsets if isinstance(toolset, AgentToolset)
    ]
    assert "summarizer" in toolset_names
