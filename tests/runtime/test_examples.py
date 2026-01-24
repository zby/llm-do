"""Smoke tests for representative examples/ patterns."""
from pathlib import Path

import pytest

from llm_do.runtime import (
    AgentEntry,
    EntryFunction,
    EntryToolset,
    ToolsetBuildContext,
    build_entry,
    load_toolsets_from_files,
    load_worker_file,
)
from llm_do.toolsets.loader import instantiate_toolsets


def _get_toolset_name(toolset):
    """Get the name of a toolset, handling EntryToolset wrappers."""
    if isinstance(toolset, EntryToolset):
        return toolset.entry.name
    return getattr(toolset, "name", None)


def _instantiate_entry_toolsets(entry_instance: AgentEntry):
    return instantiate_toolsets(
        entry_instance.toolset_specs,
        entry_instance.toolset_context or ToolsetBuildContext(worker_name=entry_instance.name),
    )


EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


@pytest.mark.anyio
async def test_single_worker_example_builds():
    worker_file = load_worker_file(EXAMPLES_DIR / "calculator" / "main.worker")
    assert "calc_tools" in worker_file.toolsets

    toolsets = load_toolsets_from_files([EXAMPLES_DIR / "calculator" / "tools.py"])
    assert "calc_tools" in toolsets

    project_root = EXAMPLES_DIR / "calculator"
    entry_instance = build_entry(
        [str(project_root / "main.worker")],
        [str(project_root / "tools.py")],
        project_root=project_root,
    )
    assert isinstance(entry_instance, AgentEntry)
    assert len(entry_instance.toolset_specs) == 1


@pytest.mark.anyio
async def test_delegation_example_builds():
    project_root = EXAMPLES_DIR / "pitchdeck_eval"
    entry_instance = build_entry(
        [
            str(project_root / "main.worker"),
            str(project_root / "pitch_evaluator.worker"),
        ],
        [],
        project_root=project_root,
    )
    assert isinstance(entry_instance, AgentEntry)
    toolset_names = [_get_toolset_name(ts) for ts in _instantiate_entry_toolsets(entry_instance)]
    assert "pitch_evaluator" in toolset_names


@pytest.mark.anyio
async def test_code_entry_example_builds():
    project_root = EXAMPLES_DIR / "pitchdeck_eval_code_entry"
    entry_instance = build_entry(
        [str(project_root / "pitch_evaluator.worker")],
        [str(project_root / "tools.py")],
        project_root=project_root,
    )
    assert isinstance(entry_instance, EntryFunction)


@pytest.mark.anyio
async def test_server_side_tools_example_builds():
    worker_file = load_worker_file(EXAMPLES_DIR / "web_searcher" / "main.worker")
    assert len(worker_file.server_side_tools) == 1
    assert worker_file.server_side_tools[0]["tool_type"] == "web_search"

    project_root = EXAMPLES_DIR / "web_searcher"
    entry_instance = build_entry(
        [str(project_root / "main.worker")],
        [],
        project_root=project_root,
    )
    assert isinstance(entry_instance, AgentEntry)
    assert len(entry_instance.builtin_tools) == 1


@pytest.mark.anyio
async def test_file_organizer_example_builds():
    """Test file_organizer: stabilizing pattern with semantic/mechanical separation."""
    worker_file = load_worker_file(EXAMPLES_DIR / "file_organizer" / "main.worker")
    assert "file_tools" in worker_file.toolsets
    assert "shell_file_ops" in worker_file.toolsets

    toolsets = load_toolsets_from_files([EXAMPLES_DIR / "file_organizer" / "tools.py"])
    assert "file_tools" in toolsets

    project_root = EXAMPLES_DIR / "file_organizer"
    entry_instance = build_entry(
        [str(project_root / "main.worker")],
        [str(project_root / "tools.py")],
        project_root=project_root,
    )
    assert isinstance(entry_instance, AgentEntry)
    assert len(entry_instance.toolset_specs) == 2


@pytest.mark.anyio
async def test_recursive_summarizer_example_builds():
    worker_file = load_worker_file(EXAMPLES_DIR / "recursive_summarizer" / "main.worker")
    assert "filesystem_project" in worker_file.toolsets
    assert "summarizer" in worker_file.toolsets

    project_root = EXAMPLES_DIR / "recursive_summarizer"
    entry_instance = build_entry(
        [
            str(project_root / "main.worker"),
            str(project_root / "summarizer.worker"),
        ],
        [],
        project_root=project_root,
    )
    assert isinstance(entry_instance, AgentEntry)
    toolset_names = [_get_toolset_name(ts) for ts in _instantiate_entry_toolsets(entry_instance)]
    assert "summarizer" in toolset_names
