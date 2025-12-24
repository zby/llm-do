"""Integration tests for examples/ using the ctx_runtime.

These tests verify that the example workers in examples/ directory
can be loaded and executed successfully using the new context-centric runtime.
"""
import pytest
from pathlib import Path
from pydantic_ai.models.test import TestModel

from llm_do.ctx_runtime import (
    Context,
    WorkerEntry,
    ToolEntry,
    load_worker_file,
    load_toolsets_from_files,
)


EXAMPLES_NEW_DIR = Path(__file__).parent.parent.parent / "examples"


class TestGreeterExample:
    """Tests for the greeter example (no tools)."""

    def test_greeter_worker_loads(self):
        """Test that the greeter worker file loads correctly."""
        worker_path = EXAMPLES_NEW_DIR / "greeter" / "main.worker"
        worker_file = load_worker_file(worker_path)

        assert worker_file.name == "main"
        assert worker_file.model == "anthropic:claude-haiku-4-5"
        assert worker_file.toolsets == {}
        assert "greeter" in worker_file.instructions.lower()

    @pytest.mark.anyio
    async def test_greeter_executes(self):
        """Test that the greeter worker executes successfully."""
        worker_path = EXAMPLES_NEW_DIR / "greeter" / "main.worker"
        worker_file = load_worker_file(worker_path)

        # Use TestModel for predictable output
        model = TestModel(custom_output_text="Hello! Nice to meet you!")

        worker = WorkerEntry(
            name=worker_file.name,
            instructions=worker_file.instructions,
            model=model,
            toolsets=[],
        )

        ctx = Context.from_entry(worker)
        result = await ctx.run(worker, {"input": "Hello, my name is Alice"})

        assert result is not None
        assert "Hello" in result


class TestCalculatorExample:
    """Tests for the calculator example (with FunctionToolset)."""

    def test_calculator_worker_loads(self):
        """Test that the calculator worker file loads correctly."""
        worker_path = EXAMPLES_NEW_DIR / "calculator" / "main.worker"
        worker_file = load_worker_file(worker_path)

        assert worker_file.name == "main"
        assert worker_file.model == "anthropic:claude-haiku-4-5"
        assert "calc_tools" in worker_file.toolsets
        # Calculator tools are pre-approved for convenience
        assert "_approval_config" in worker_file.toolsets["calc_tools"]

    def test_calculator_tools_load(self):
        """Test that the calculator tools can be discovered."""
        tools_path = EXAMPLES_NEW_DIR / "calculator" / "tools.py"
        toolsets = load_toolsets_from_files([tools_path])

        assert "calc_tools" in toolsets

        # Check it's a FunctionToolset
        from pydantic_ai.toolsets import FunctionToolset
        assert isinstance(toolsets["calc_tools"], FunctionToolset)

    @pytest.mark.anyio
    async def test_calculator_tools_via_context(self):
        """Test calling calculator tools via context."""
        tools_path = EXAMPLES_NEW_DIR / "calculator" / "tools.py"
        toolsets = load_toolsets_from_files([tools_path])
        calc_toolset = toolsets["calc_tools"]

        ctx = Context(toolsets=[calc_toolset], model="test-model")

        # Call factorial(5) = 120
        result = await ctx.call("factorial", {"n": 5})
        assert result == 120

        # Call factorial(7) = 5040
        result = await ctx.call("factorial", {"n": 7})
        assert result == 5040

    @pytest.mark.anyio
    async def test_calculator_fibonacci_tool(self):
        """Test that the fibonacci tool works correctly."""
        tools_path = EXAMPLES_NEW_DIR / "calculator" / "tools.py"
        toolsets = load_toolsets_from_files([tools_path])
        calc_toolset = toolsets["calc_tools"]

        ctx = Context(toolsets=[calc_toolset], model="test-model")

        # Fibonacci sequence: 0, 1, 1, 2, 3, 5, 8, 13, 21, 34
        assert await ctx.call("fibonacci", {"n": 0}) == 0
        assert await ctx.call("fibonacci", {"n": 1}) == 1
        assert await ctx.call("fibonacci", {"n": 10}) == 55

    @pytest.mark.anyio
    async def test_calculator_add_multiply_tools(self):
        """Test the add and multiply tools."""
        tools_path = EXAMPLES_NEW_DIR / "calculator" / "tools.py"
        toolsets = load_toolsets_from_files([tools_path])
        calc_toolset = toolsets["calc_tools"]

        ctx = Context(toolsets=[calc_toolset], model="test-model")

        assert await ctx.call("add", {"a": 3, "b": 4}) == 7
        assert await ctx.call("multiply", {"a": 3, "b": 4}) == 12

    @pytest.mark.anyio
    async def test_calculator_worker_with_tools(self):
        """Test the full calculator worker with tool calling."""
        from llm_do.ctx_runtime.cli import build_entry

        worker_path = str(EXAMPLES_NEW_DIR / "calculator" / "main.worker")
        tools_path = str(EXAMPLES_NEW_DIR / "calculator" / "tools.py")

        # Build worker with tools
        worker = await build_entry(
            [worker_path],
            [tools_path],
            model=TestModel(
                call_tools=["factorial"],
                custom_output_text="The factorial of 5 is 120.",
            ),
        )

        assert worker.name == "main"
        assert len(worker.toolsets) == 1  # calc_tools toolset


class TestApprovalsDemoExample:
    """Tests for the approvals_demo example (filesystem toolset)."""

    def test_approvals_demo_worker_loads(self):
        """Test that the approvals_demo worker file loads correctly."""
        worker_path = EXAMPLES_NEW_DIR / "approvals_demo" / "main.worker"
        worker_file = load_worker_file(worker_path)

        assert worker_file.name == "main"
        assert worker_file.model == "anthropic:claude-haiku-4-5"
        assert "filesystem" in worker_file.toolsets
        assert "notes" in worker_file.instructions.lower()

    @pytest.mark.anyio
    async def test_approvals_demo_builds_with_filesystem(self):
        """Test that approvals_demo worker builds with filesystem toolset."""
        from llm_do.ctx_runtime.cli import build_entry

        worker_path = str(EXAMPLES_NEW_DIR / "approvals_demo" / "main.worker")

        worker = await build_entry(
            [worker_path],
            [],
            model="anthropic:claude-haiku-4-5",
        )

        assert worker.name == "main"
        # Should have filesystem toolset
        assert len(worker.toolsets) >= 1


class TestCodeAnalyzerExample:
    """Tests for the code_analyzer example (shell toolset)."""

    def test_code_analyzer_worker_loads(self):
        """Test that the code_analyzer worker file loads correctly."""
        worker_path = EXAMPLES_NEW_DIR / "code_analyzer" / "main.worker"
        worker_file = load_worker_file(worker_path)

        assert worker_file.name == "main"
        assert worker_file.model == "anthropic:claude-haiku-4-5"
        assert "shell" in worker_file.toolsets
        # Should have rules for whitelisted commands
        assert "rules" in worker_file.toolsets["shell"]
        assert len(worker_file.toolsets["shell"]["rules"]) > 0

    @pytest.mark.anyio
    async def test_code_analyzer_builds_with_shell(self):
        """Test that code_analyzer worker builds with shell toolset."""
        from llm_do.ctx_runtime.cli import build_entry

        worker_path = str(EXAMPLES_NEW_DIR / "code_analyzer" / "main.worker")

        worker = await build_entry(
            [worker_path],
            [],
            model="anthropic:claude-haiku-4-5",
        )

        assert worker.name == "main"
        # Should have shell toolset
        assert len(worker.toolsets) >= 1


class TestPitchdeckEvalExample:
    """Tests for the pitchdeck_eval example (delegation)."""

    def test_pitchdeck_main_worker_loads(self):
        """Test that the pitchdeck main worker file loads correctly."""
        worker_path = EXAMPLES_NEW_DIR / "pitchdeck_eval" / "main.worker"
        worker_file = load_worker_file(worker_path)

        assert worker_file.name == "main"
        assert worker_file.model == "anthropic:claude-haiku-4-5"
        assert "pitch_evaluator" in worker_file.toolsets
        assert "filesystem" in worker_file.toolsets

    def test_pitchdeck_evaluator_worker_loads(self):
        """Test that the pitch_evaluator worker file loads correctly."""
        worker_path = EXAMPLES_NEW_DIR / "pitchdeck_eval" / "pitch_evaluator.worker"
        worker_file = load_worker_file(worker_path)

        assert worker_file.name == "pitch_evaluator"
        assert worker_file.model == "anthropic:claude-haiku-4-5"
        assert "evaluation" in worker_file.instructions.lower()

    @pytest.mark.anyio
    async def test_pitchdeck_builds_with_delegation(self):
        """Test that pitchdeck_eval main worker builds with workers as toolsets."""
        from llm_do.ctx_runtime.cli import build_entry

        main_path = str(EXAMPLES_NEW_DIR / "pitchdeck_eval" / "main.worker")
        eval_path = str(EXAMPLES_NEW_DIR / "pitchdeck_eval" / "pitch_evaluator.worker")

        # build_entry handles worker resolution automatically
        worker = await build_entry(
            [main_path, eval_path],
            [],
            model="anthropic:claude-haiku-4-5",
        )

        assert worker.name == "main"
        # Should have pitch_evaluator and filesystem toolsets
        assert len(worker.toolsets) >= 2

        # Check that pitch_evaluator is available as a toolset
        toolset_ids = [getattr(ts, 'id', None) or getattr(ts, 'name', None) for ts in worker.toolsets]
        assert "pitch_evaluator" in toolset_ids


class TestWhiteboardPlannerExample:
    """Tests for the whiteboard_planner example (delegation)."""

    def test_whiteboard_main_worker_loads(self):
        """Test that the whiteboard main worker file loads correctly."""
        worker_path = EXAMPLES_NEW_DIR / "whiteboard_planner" / "main.worker"
        worker_file = load_worker_file(worker_path)

        assert worker_file.name == "main"
        assert worker_file.model == "anthropic:claude-haiku-4-5"
        assert "whiteboard_planner" in worker_file.toolsets
        assert "filesystem" in worker_file.toolsets

    def test_whiteboard_planner_worker_loads(self):
        """Test that the whiteboard_planner worker file loads correctly."""
        worker_path = EXAMPLES_NEW_DIR / "whiteboard_planner" / "whiteboard_planner.worker"
        worker_file = load_worker_file(worker_path)

        assert worker_file.name == "whiteboard_planner"
        assert worker_file.model == "anthropic:claude-haiku-4-5"
        assert "project" in worker_file.instructions.lower()

    @pytest.mark.anyio
    async def test_whiteboard_builds_with_delegation(self):
        """Test that whiteboard_planner main worker builds with workers as toolsets."""
        from llm_do.ctx_runtime.cli import build_entry

        main_path = str(EXAMPLES_NEW_DIR / "whiteboard_planner" / "main.worker")
        planner_path = str(EXAMPLES_NEW_DIR / "whiteboard_planner" / "whiteboard_planner.worker")

        # build_entry handles worker resolution automatically
        worker = await build_entry(
            [main_path, planner_path],
            [],
            model="anthropic:claude-haiku-4-5",
        )

        assert worker.name == "main"
        # Should have whiteboard_planner and filesystem toolsets
        assert len(worker.toolsets) >= 2

        toolset_ids = [getattr(ts, 'id', None) or getattr(ts, 'name', None) for ts in worker.toolsets]
        assert "whiteboard_planner" in toolset_ids


class TestExamplesIntegration:
    """Integration tests verifying the full CLI flow."""

    @pytest.mark.anyio
    async def test_build_worker_greeter(self):
        """Test building the greeter worker via CLI helper."""
        from llm_do.ctx_runtime.cli import build_entry

        worker_path = str(EXAMPLES_NEW_DIR / "greeter" / "main.worker")

        worker = await build_entry(
            [worker_path],
            [],
            model="anthropic:claude-haiku-4-5",
        )

        assert worker.name == "main"
        assert worker.toolsets == []
        assert "greeter" in worker.instructions.lower()

    @pytest.mark.anyio
    async def test_build_worker_calculator(self):
        """Test building the calculator worker via CLI helper."""
        from llm_do.ctx_runtime.cli import build_entry

        worker_path = str(EXAMPLES_NEW_DIR / "calculator" / "main.worker")
        tools_path = str(EXAMPLES_NEW_DIR / "calculator" / "tools.py")

        worker = await build_entry(
            [worker_path],
            [tools_path],
            model="anthropic:claude-haiku-4-5",
        )

        assert worker.name == "main"
        assert len(worker.toolsets) == 1
        assert "calculator" in worker.instructions.lower()


class TestPitchdeckEvalCodeEntryExample:
    """Tests for the pitchdeck_eval_code_entry example (code entry point pattern)."""

    def test_toolset_loads(self):
        """Test that the tools.py toolset loads correctly."""
        tools_path = EXAMPLES_NEW_DIR / "pitchdeck_eval_code_entry" / "tools.py"
        toolsets = load_toolsets_from_files([str(tools_path)])

        assert "tools" in toolsets
        toolset = toolsets["tools"]
        # Should have 'main' tool
        assert "main" in toolset.tools

    @pytest.mark.anyio
    async def test_code_entry_builds_with_worker(self):
        """Test that code entry point builds with worker as available toolset."""
        from llm_do.ctx_runtime.cli import build_entry

        tools_path = str(EXAMPLES_NEW_DIR / "pitchdeck_eval_code_entry" / "tools.py")
        worker_path = str(EXAMPLES_NEW_DIR / "pitchdeck_eval_code_entry" / "pitch_evaluator.worker")

        # Build with 'main' as entry (code entry point)
        entry = await build_entry(
            [worker_path],
            [tools_path],
            model="anthropic:claude-haiku-4-5",
            entry_name="main",
        )

        # Entry should be a ToolEntry (code entry point)
        assert isinstance(entry, ToolEntry)
        assert entry.name == "main"

        # entry.toolsets should include pitch_evaluator (as WorkerEntry)
        toolset_ids = [getattr(ts, 'id', None) or getattr(ts, 'name', None) for ts in entry.toolsets]
        assert "pitch_evaluator" in toolset_ids

    @pytest.mark.anyio
    async def test_code_entry_can_call_worker_via_context(self):
        """Test that code entry can call worker through context."""
        from pydantic_ai.models.test import TestModel
        from llm_do.ctx_runtime.cli import build_entry

        tools_path = str(EXAMPLES_NEW_DIR / "pitchdeck_eval_code_entry" / "tools.py")
        worker_path = str(EXAMPLES_NEW_DIR / "pitchdeck_eval_code_entry" / "pitch_evaluator.worker")

        entry = await build_entry(
            [worker_path],
            [tools_path],
            model="anthropic:claude-haiku-4-5",
            entry_name="main",
        )

        # entry.toolsets is now populated by build_entry
        assert len(entry.toolsets) > 0

        # Find and override the worker's model with TestModel
        pitch_evaluator = next(
            ts for ts in entry.toolsets
            if getattr(ts, 'name', None) == "pitch_evaluator"
        )
        assert isinstance(pitch_evaluator, WorkerEntry)
        pitch_evaluator.model = TestModel(custom_output_text="Evaluation complete.")

        # Create context - entry.toolsets is already populated
        ctx = Context.from_entry(entry, model=TestModel(custom_output_text="Evaluation complete."))

        # Test that we can call the worker through context
        result = await ctx.call("pitch_evaluator", {"input": "Test evaluation"})
        assert result == "Evaluation complete."
