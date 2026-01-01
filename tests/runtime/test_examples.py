"""Smoke tests for representative examples/ patterns."""
from pathlib import Path

import pytest

from llm_do.cli.main import build_entry
from llm_do.runtime import (
    ToolInvocable,
    load_toolsets_from_files,
    load_worker_file,
)

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


@pytest.mark.anyio
async def test_single_worker_example_builds():
    worker_file = load_worker_file(EXAMPLES_DIR / "calculator" / "main.worker")
    assert "calc_tools" in worker_file.toolsets

    toolsets = load_toolsets_from_files([EXAMPLES_DIR / "calculator" / "tools.py"])
    assert "calc_tools" in toolsets

    worker = await build_entry(
        [str(EXAMPLES_DIR / "calculator" / "main.worker")],
        [str(EXAMPLES_DIR / "calculator" / "tools.py")],
        model="test-model",
    )
    assert len(worker.toolsets) == 1


@pytest.mark.anyio
async def test_delegation_example_builds():
    worker = await build_entry(
        [
            str(EXAMPLES_DIR / "pitchdeck_eval" / "main.worker"),
            str(EXAMPLES_DIR / "pitchdeck_eval" / "pitch_evaluator.worker"),
        ],
        [],
        model="test-model",
    )
    toolset_names = [getattr(ts, "name", None) for ts in worker.toolsets]
    assert "pitch_evaluator" in toolset_names


@pytest.mark.anyio
async def test_code_entry_example_builds():
    entry = await build_entry(
        [str(EXAMPLES_DIR / "pitchdeck_eval_code_entry" / "pitch_evaluator.worker")],
        [str(EXAMPLES_DIR / "pitchdeck_eval_code_entry" / "tools.py")],
        model="test-model",
        entry_name="main",
    )
    assert isinstance(entry, ToolInvocable)


@pytest.mark.anyio
async def test_server_side_tools_example_builds():
    worker_file = load_worker_file(EXAMPLES_DIR / "web_searcher" / "main.worker")
    assert len(worker_file.server_side_tools) == 1
    assert worker_file.server_side_tools[0]["tool_type"] == "web_search"

    worker = await build_entry(
        [str(EXAMPLES_DIR / "web_searcher" / "main.worker")],
        [],
        model="test-model",
    )
    assert len(worker.builtin_tools) == 1


@pytest.mark.anyio
async def test_file_organizer_example_builds():
    """Test file_organizer: hardening pattern with semantic/mechanical separation."""
    worker_file = load_worker_file(EXAMPLES_DIR / "file_organizer" / "main.worker")
    assert "file_tools" in worker_file.toolsets
    assert "shell" in worker_file.toolsets

    toolsets = load_toolsets_from_files([EXAMPLES_DIR / "file_organizer" / "tools.py"])
    assert "file_tools" in toolsets

    worker = await build_entry(
        [str(EXAMPLES_DIR / "file_organizer" / "main.worker")],
        [str(EXAMPLES_DIR / "file_organizer" / "tools.py")],
        model="test-model",
    )
    assert len(worker.toolsets) == 2  # file_tools + shell
