"""Smoke tests for representative examples/ patterns."""
from pathlib import Path

import pytest

from llm_do.runtime import (
    EntryFunction,
    ToolsetBuildContext,
    build_entry,
    load_toolsets_from_files,
    load_worker_file,
)
from llm_do.runtime.worker import WorkerToolset
from llm_do.toolsets.loader import instantiate_toolsets


def _get_toolset_name(toolset):
    """Get the name of a toolset, handling WorkerToolset wrappers."""
    if isinstance(toolset, WorkerToolset):
        return toolset.worker.name
    return getattr(toolset, "name", None)


def _instantiate_worker_toolsets(worker):
    return instantiate_toolsets(
        worker.toolset_specs,
        worker.toolset_context or ToolsetBuildContext(worker_name=worker.name),
    )

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


@pytest.mark.anyio
async def test_single_worker_example_builds():
    worker_file = load_worker_file(EXAMPLES_DIR / "calculator" / "main.worker")
    assert "calc_tools" in worker_file.toolsets

    toolsets = load_toolsets_from_files([EXAMPLES_DIR / "calculator" / "tools.py"])
    assert "calc_tools" in toolsets

    entry = build_entry(
        [str(EXAMPLES_DIR / "calculator" / "main.worker")],
        [str(EXAMPLES_DIR / "calculator" / "tools.py")],
        entry_model_override="test-model",
    )
    worker = entry
    assert len(worker.toolset_specs) == 1


@pytest.mark.anyio
async def test_delegation_example_builds():
    entry = build_entry(
        [
            str(EXAMPLES_DIR / "pitchdeck_eval" / "main.worker"),
            str(EXAMPLES_DIR / "pitchdeck_eval" / "pitch_evaluator.worker"),
        ],
        [],
        entry_model_override="test-model",
    )
    worker = entry
    toolset_names = [_get_toolset_name(ts) for ts in _instantiate_worker_toolsets(worker)]
    assert "pitch_evaluator" in toolset_names


@pytest.mark.anyio
async def test_code_entry_example_builds():
    entry = build_entry(
        [str(EXAMPLES_DIR / "pitchdeck_eval_code_entry" / "pitch_evaluator.worker")],
        [str(EXAMPLES_DIR / "pitchdeck_eval_code_entry" / "tools.py")],
        entry_model_override="test-model",
    )
    assert isinstance(entry, EntryFunction)


@pytest.mark.anyio
async def test_server_side_tools_example_builds():
    worker_file = load_worker_file(EXAMPLES_DIR / "web_searcher" / "main.worker")
    assert len(worker_file.server_side_tools) == 1
    assert worker_file.server_side_tools[0]["tool_type"] == "web_search"

    entry = build_entry(
        [str(EXAMPLES_DIR / "web_searcher" / "main.worker")],
        [],
        entry_model_override="test-model",
    )
    worker = entry
    assert len(worker.builtin_tools) == 1


@pytest.mark.anyio
async def test_file_organizer_example_builds():
    """Test file_organizer: stabilizing pattern with semantic/mechanical separation."""
    worker_file = load_worker_file(EXAMPLES_DIR / "file_organizer" / "main.worker")
    assert "file_tools" in worker_file.toolsets
    assert "shell_file_ops" in worker_file.toolsets

    toolsets = load_toolsets_from_files([EXAMPLES_DIR / "file_organizer" / "tools.py"])
    assert "file_tools" in toolsets

    entry = build_entry(
        [str(EXAMPLES_DIR / "file_organizer" / "main.worker")],
        [str(EXAMPLES_DIR / "file_organizer" / "tools.py")],
        entry_model_override="test-model",
    )
    worker = entry
    assert len(worker.toolset_specs) == 2  # file_tools + shell_file_ops


@pytest.mark.anyio
async def test_recursive_summarizer_example_builds():
    worker_file = load_worker_file(EXAMPLES_DIR / "recursive_summarizer" / "main.worker")
    assert "filesystem_project" in worker_file.toolsets
    assert "summarizer" in worker_file.toolsets

    entry = build_entry(
        [
            str(EXAMPLES_DIR / "recursive_summarizer" / "main.worker"),
            str(EXAMPLES_DIR / "recursive_summarizer" / "summarizer.worker"),
        ],
        [],
        entry_model_override="test-model",
    )
    worker = entry
    toolset_names = [_get_toolset_name(ts) for ts in _instantiate_worker_toolsets(worker)]
    assert "summarizer" in toolset_names
