"""Smoke tests for representative examples/ patterns."""
from pathlib import Path

import pytest

from llm_do.runtime import (
    ToolInvocable,
    build_invocable_registry,
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

    registry = await build_invocable_registry(
        [str(EXAMPLES_DIR / "calculator" / "main.worker")],
        [str(EXAMPLES_DIR / "calculator" / "tools.py")],
        entry_name="main",
        entry_model_override="test-model",
    )
    worker = registry.get("main")
    assert len(worker.toolsets) == 1


@pytest.mark.anyio
async def test_delegation_example_builds():
    registry = await build_invocable_registry(
        [
            str(EXAMPLES_DIR / "pitchdeck_eval" / "main.worker"),
            str(EXAMPLES_DIR / "pitchdeck_eval" / "pitch_evaluator.worker"),
        ],
        [],
        entry_name="main",
        entry_model_override="test-model",
    )
    worker = registry.get("main")
    toolset_names = [getattr(ts, "name", None) for ts in worker.toolsets]
    assert "pitch_evaluator" in toolset_names


@pytest.mark.anyio
async def test_code_entry_example_builds():
    registry = await build_invocable_registry(
        [str(EXAMPLES_DIR / "pitchdeck_eval_code_entry" / "pitch_evaluator.worker")],
        [str(EXAMPLES_DIR / "pitchdeck_eval_code_entry" / "tools.py")],
        entry_name="main",
        entry_model_override="test-model",
    )
    entry = registry.get("main")
    assert isinstance(entry, ToolInvocable)


@pytest.mark.anyio
async def test_server_side_tools_example_builds():
    worker_file = load_worker_file(EXAMPLES_DIR / "web_searcher" / "main.worker")
    assert len(worker_file.server_side_tools) == 1
    assert worker_file.server_side_tools[0]["tool_type"] == "web_search"

    registry = await build_invocable_registry(
        [str(EXAMPLES_DIR / "web_searcher" / "main.worker")],
        [],
        entry_name="main",
        entry_model_override="test-model",
    )
    worker = registry.get("main")
    assert len(worker.builtin_tools) == 1


@pytest.mark.anyio
async def test_file_organizer_example_builds():
    """Test file_organizer: hardening pattern with semantic/mechanical separation."""
    worker_file = load_worker_file(EXAMPLES_DIR / "file_organizer" / "main.worker")
    assert "file_tools" in worker_file.toolsets
    assert "shell_file_ops" in worker_file.toolsets

    toolsets = load_toolsets_from_files([EXAMPLES_DIR / "file_organizer" / "tools.py"])
    assert "file_tools" in toolsets

    registry = await build_invocable_registry(
        [str(EXAMPLES_DIR / "file_organizer" / "main.worker")],
        [str(EXAMPLES_DIR / "file_organizer" / "tools.py")],
        entry_name="main",
        entry_model_override="test-model",
    )
    worker = registry.get("main")
    assert len(worker.toolsets) == 2  # file_tools + shell_file_ops
