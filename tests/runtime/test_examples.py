"""Smoke tests for examples/ directory.

These tests verify that example workers can be loaded and built correctly.
They do NOT test execution - just that the configuration is valid.
"""
import pytest
from pathlib import Path

from llm_do.ctx_runtime import (
    WorkerEntry,
    ToolEntry,
    load_worker_file,
    load_toolsets_from_files,
)
from llm_do.ctx_runtime.cli import build_entry


EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


class TestGreeterExample:
    """Smoke tests for greeter example."""

    def test_worker_loads(self):
        worker_file = load_worker_file(EXAMPLES_DIR / "greeter" / "main.worker")
        assert worker_file.name == "main"
        assert worker_file.toolsets == {}

    @pytest.mark.anyio
    async def test_builds(self):
        worker = await build_entry(
            [str(EXAMPLES_DIR / "greeter" / "main.worker")],
            [],
            model="test-model",
        )
        assert worker.name == "main"
        assert worker.toolsets == []


class TestCalculatorExample:
    """Smoke tests for calculator example."""

    def test_worker_loads(self):
        worker_file = load_worker_file(EXAMPLES_DIR / "calculator" / "main.worker")
        assert worker_file.name == "main"
        assert "calc_tools" in worker_file.toolsets

    def test_tools_load(self):
        toolsets = load_toolsets_from_files([EXAMPLES_DIR / "calculator" / "tools.py"])
        assert "calc_tools" in toolsets

    @pytest.mark.anyio
    async def test_builds(self):
        worker = await build_entry(
            [str(EXAMPLES_DIR / "calculator" / "main.worker")],
            [str(EXAMPLES_DIR / "calculator" / "tools.py")],
            model="test-model",
        )
        assert worker.name == "main"
        assert len(worker.toolsets) == 1


class TestApprovalsDemoExample:
    """Smoke tests for approvals_demo example."""

    def test_worker_loads(self):
        worker_file = load_worker_file(EXAMPLES_DIR / "approvals_demo" / "main.worker")
        assert worker_file.name == "main"
        assert "filesystem" in worker_file.toolsets

    @pytest.mark.anyio
    async def test_builds(self):
        worker = await build_entry(
            [str(EXAMPLES_DIR / "approvals_demo" / "main.worker")],
            [],
            model="test-model",
        )
        assert worker.name == "main"
        assert len(worker.toolsets) >= 1


class TestCodeAnalyzerExample:
    """Smoke tests for code_analyzer example."""

    def test_worker_loads(self):
        worker_file = load_worker_file(EXAMPLES_DIR / "code_analyzer" / "main.worker")
        assert worker_file.name == "main"
        assert "shell" in worker_file.toolsets
        assert "rules" in worker_file.toolsets["shell"]

    @pytest.mark.anyio
    async def test_builds(self):
        worker = await build_entry(
            [str(EXAMPLES_DIR / "code_analyzer" / "main.worker")],
            [],
            model="test-model",
        )
        assert worker.name == "main"
        assert len(worker.toolsets) >= 1


class TestPitchdeckEvalExample:
    """Smoke tests for pitchdeck_eval example (delegation pattern)."""

    def test_main_worker_loads(self):
        worker_file = load_worker_file(EXAMPLES_DIR / "pitchdeck_eval" / "main.worker")
        assert worker_file.name == "main"
        assert "pitch_evaluator" in worker_file.toolsets
        assert "filesystem" in worker_file.toolsets

    def test_evaluator_worker_loads(self):
        worker_file = load_worker_file(EXAMPLES_DIR / "pitchdeck_eval" / "pitch_evaluator.worker")
        assert worker_file.name == "pitch_evaluator"

    @pytest.mark.anyio
    async def test_builds_with_delegation(self):
        worker = await build_entry(
            [
                str(EXAMPLES_DIR / "pitchdeck_eval" / "main.worker"),
                str(EXAMPLES_DIR / "pitchdeck_eval" / "pitch_evaluator.worker"),
            ],
            [],
            model="test-model",
        )
        assert worker.name == "main"
        toolset_names = [getattr(ts, 'name', None) for ts in worker.toolsets]
        assert "pitch_evaluator" in toolset_names


class TestPitchdeckEvalHardenedExample:
    """Smoke tests for pitchdeck_eval_hardened example."""

    def test_main_worker_loads(self):
        worker_file = load_worker_file(EXAMPLES_DIR / "pitchdeck_eval_hardened" / "main.worker")
        assert worker_file.name == "main"
        assert "pitch_evaluator" in worker_file.toolsets
        assert "pitchdeck_tools" in worker_file.toolsets

    def test_tools_load(self):
        toolsets = load_toolsets_from_files([EXAMPLES_DIR / "pitchdeck_eval_hardened" / "tools.py"])
        assert "pitchdeck_tools" in toolsets

    @pytest.mark.anyio
    async def test_builds(self):
        worker = await build_entry(
            [
                str(EXAMPLES_DIR / "pitchdeck_eval_hardened" / "main.worker"),
                str(EXAMPLES_DIR / "pitchdeck_eval_hardened" / "pitch_evaluator.worker"),
            ],
            [str(EXAMPLES_DIR / "pitchdeck_eval_hardened" / "tools.py")],
            model="test-model",
        )
        assert worker.name == "main"


class TestPitchdeckEvalCodeEntryExample:
    """Smoke tests for pitchdeck_eval_code_entry example (code entry pattern)."""

    def test_tools_load(self):
        toolsets = load_toolsets_from_files([EXAMPLES_DIR / "pitchdeck_eval_code_entry" / "tools.py"])
        assert "tools" in toolsets
        assert "main" in toolsets["tools"].tools

    def test_worker_loads(self):
        worker_file = load_worker_file(EXAMPLES_DIR / "pitchdeck_eval_code_entry" / "pitch_evaluator.worker")
        assert worker_file.name == "pitch_evaluator"

    @pytest.mark.anyio
    async def test_builds_as_code_entry(self):
        entry = await build_entry(
            [str(EXAMPLES_DIR / "pitchdeck_eval_code_entry" / "pitch_evaluator.worker")],
            [str(EXAMPLES_DIR / "pitchdeck_eval_code_entry" / "tools.py")],
            model="test-model",
            entry_name="main",
        )
        assert isinstance(entry, ToolEntry)
        assert entry.name == "main"


class TestWhiteboardPlannerExample:
    """Smoke tests for whiteboard_planner example (delegation pattern)."""

    def test_main_worker_loads(self):
        worker_file = load_worker_file(EXAMPLES_DIR / "whiteboard_planner" / "main.worker")
        assert worker_file.name == "main"
        assert "whiteboard_planner" in worker_file.toolsets

    def test_planner_worker_loads(self):
        worker_file = load_worker_file(EXAMPLES_DIR / "whiteboard_planner" / "whiteboard_planner.worker")
        assert worker_file.name == "whiteboard_planner"

    @pytest.mark.anyio
    async def test_builds_with_delegation(self):
        worker = await build_entry(
            [
                str(EXAMPLES_DIR / "whiteboard_planner" / "main.worker"),
                str(EXAMPLES_DIR / "whiteboard_planner" / "whiteboard_planner.worker"),
            ],
            [],
            model="test-model",
        )
        assert worker.name == "main"
        toolset_names = [getattr(ts, 'name', None) for ts in worker.toolsets]
        assert "whiteboard_planner" in toolset_names


class TestWebResearchAgentExample:
    """Smoke tests for web_research_agent example (complex multi-worker)."""

    def test_main_worker_loads(self):
        worker_file = load_worker_file(EXAMPLES_DIR / "web_research_agent" / "main.worker")
        assert worker_file.name == "main"
        assert "web_research_extractor" in worker_file.toolsets

    def test_tools_load(self):
        toolsets = load_toolsets_from_files([EXAMPLES_DIR / "web_research_agent" / "tools.py"])
        assert "web_research_tools" in toolsets

    @pytest.mark.anyio
    async def test_builds(self):
        worker = await build_entry(
            [
                str(EXAMPLES_DIR / "web_research_agent" / "main.worker"),
                str(EXAMPLES_DIR / "web_research_agent" / "web_research_extractor.worker"),
                str(EXAMPLES_DIR / "web_research_agent" / "web_research_consolidator.worker"),
                str(EXAMPLES_DIR / "web_research_agent" / "web_research_reporter.worker"),
            ],
            [str(EXAMPLES_DIR / "web_research_agent" / "tools.py")],
            model="test-model",
        )
        assert worker.name == "main"


class TestWebSearcherExample:
    """Smoke tests for web_searcher example (server_side_tools)."""

    def test_worker_loads(self):
        worker_file = load_worker_file(EXAMPLES_DIR / "web_searcher" / "main.worker")
        assert worker_file.name == "main"
        assert len(worker_file.server_side_tools) == 1
        assert worker_file.server_side_tools[0]["tool_type"] == "web_search"

    @pytest.mark.anyio
    async def test_builds(self):
        worker = await build_entry(
            [str(EXAMPLES_DIR / "web_searcher" / "main.worker")],
            [],
            model="test-model",
        )
        assert worker.name == "main"
        assert len(worker.builtin_tools) == 1
