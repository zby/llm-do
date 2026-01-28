"""Smoke tests for representative examples/ patterns."""
from pathlib import Path

import pytest

from llm_do.runtime import (
    build_registry,
    load_agent_file,
    load_manifest,
    load_toolsets_from_files,
    resolve_entry,
    resolve_manifest_paths,
)
from llm_do.toolsets.agent import AgentToolset
from llm_do.toolsets.dynamic_agents import DynamicAgentsToolset
from llm_do.toolsets.loader import instantiate_toolsets

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


def _build_example(example_name: str):
    manifest, manifest_dir = load_manifest(EXAMPLES_DIR / example_name / "project.json")
    agent_paths, python_paths = resolve_manifest_paths(manifest, manifest_dir)
    registry = build_registry(
        [str(path) for path in agent_paths],
        [str(path) for path in python_paths],
        project_root=manifest_dir,
    )
    entry = resolve_entry(
        manifest.entry,
        registry,
        python_files=python_paths,
        base_path=manifest_dir,
    )
    return entry, registry, manifest


@pytest.mark.anyio
async def test_single_worker_example_builds():
    worker_file = load_agent_file(EXAMPLES_DIR / "calculator" / "main.agent")
    assert "calc_tools" in worker_file.toolsets

    toolsets = load_toolsets_from_files([EXAMPLES_DIR / "calculator" / "tools.py"])
    assert "calc_tools" in toolsets

    entry, registry, _manifest = _build_example("calculator")
    agent = registry.agents[entry.name]
    assert len(agent.toolset_specs) == 1


@pytest.mark.anyio
async def test_delegation_example_builds():
    """Test pitchdeck_eval: static agent delegation pattern."""
    entry, registry, _manifest = _build_example("pitchdeck_eval")
    agent = registry.agents[entry.name]
    toolsets = instantiate_toolsets(
        agent.toolset_specs,
    )
    assert any(isinstance(toolset, AgentToolset) for toolset in toolsets)


@pytest.mark.anyio
async def test_bootstrapping_example_builds():
    """Test bootstrapping: dynamic agent creation pattern."""
    entry, registry, _manifest = _build_example("bootstrapping")
    agent = registry.agents[entry.name]
    toolsets = instantiate_toolsets(
        agent.toolset_specs,
    )
    assert any(isinstance(toolset, DynamicAgentsToolset) for toolset in toolsets)


@pytest.mark.anyio
async def test_code_entry_example_builds():
    entry, _registry, _manifest = _build_example("pitchdeck_eval_code_entry")
    assert entry.name


@pytest.mark.anyio
async def test_server_side_tools_example_builds():
    worker_file = load_agent_file(EXAMPLES_DIR / "web_searcher" / "main.agent")
    assert len(worker_file.server_side_tools) == 1
    assert worker_file.server_side_tools[0]["tool_type"] == "web_search"

    entry, registry, _manifest = _build_example("web_searcher")
    agent = registry.agents[entry.name]
    assert len(agent.builtin_tools) == 1


@pytest.mark.anyio
async def test_file_organizer_example_builds():
    """Test file_organizer: stabilizing pattern with semantic/mechanical separation."""
    worker_file = load_agent_file(EXAMPLES_DIR / "file_organizer" / "main.agent")
    assert "file_tools" in worker_file.toolsets
    assert "shell_file_ops" in worker_file.toolsets

    toolsets = load_toolsets_from_files([EXAMPLES_DIR / "file_organizer" / "tools.py"])
    assert "file_tools" in toolsets

    entry, registry, _manifest = _build_example("file_organizer")
    agent = registry.agents[entry.name]
    assert len(agent.toolset_specs) == 2  # file_tools + shell_file_ops


@pytest.mark.anyio
async def test_recursive_summarizer_example_builds():
    worker_file = load_agent_file(EXAMPLES_DIR / "recursive_summarizer" / "main.agent")
    assert "filesystem_project" in worker_file.toolsets
    assert "summarizer" in worker_file.toolsets

    entry, registry, _manifest = _build_example("recursive_summarizer")
    agent = registry.agents[entry.name]
    toolsets = instantiate_toolsets(
        agent.toolset_specs,
    )
    toolset_names = [
        toolset.spec.name for toolset in toolsets if isinstance(toolset, AgentToolset)
    ]
    assert "summarizer" in toolset_names
