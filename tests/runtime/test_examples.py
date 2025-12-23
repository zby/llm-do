"""Integration tests for examples-new/ using the ctx_runtime.

These tests verify that the example workers in examples-new/ directory
can be loaded and executed successfully using the new context-centric runtime.
"""
import pytest
from pathlib import Path
from pydantic_ai.models.test import TestModel

from llm_do.ctx_runtime import (
    Context,
    WorkerEntry,
    load_worker_file,
    load_toolsets_from_files,
    expand_toolset_to_entries,
)


EXAMPLES_NEW_DIR = Path(__file__).parent.parent.parent / "examples-new"


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
            tools=[],
        )

        ctx = Context.from_worker(worker)
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
        assert worker_file.toolsets["calc_tools"] == {}

    def test_calculator_tools_load(self):
        """Test that the calculator tools can be discovered."""
        tools_path = EXAMPLES_NEW_DIR / "calculator" / "tools.py"
        toolsets = load_toolsets_from_files([tools_path])

        assert "calc_tools" in toolsets

        # Check it's a FunctionToolset
        from pydantic_ai.toolsets import FunctionToolset
        assert isinstance(toolsets["calc_tools"], FunctionToolset)

    @pytest.mark.anyio
    async def test_calculator_tools_expand(self):
        """Test that calculator toolset expands to individual tools."""
        tools_path = EXAMPLES_NEW_DIR / "calculator" / "tools.py"
        toolsets = load_toolsets_from_files([tools_path])
        calc_toolset = toolsets["calc_tools"]

        entries = await expand_toolset_to_entries(calc_toolset)

        tool_names = {e.name for e in entries}
        assert "factorial" in tool_names
        assert "fibonacci" in tool_names
        assert "add" in tool_names
        assert "multiply" in tool_names

    @pytest.mark.anyio
    async def test_calculator_factorial_tool(self):
        """Test that the factorial tool works correctly."""
        tools_path = EXAMPLES_NEW_DIR / "calculator" / "tools.py"
        toolsets = load_toolsets_from_files([tools_path])
        calc_toolset = toolsets["calc_tools"]

        entries = await expand_toolset_to_entries(calc_toolset)
        factorial_entry = next(e for e in entries if e.name == "factorial")

        # Create a minimal context for tool execution
        ctx = Context.from_tool_entries(entries, model="test-model")

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

        entries = await expand_toolset_to_entries(calc_toolset)
        ctx = Context.from_tool_entries(entries, model="test-model")

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

        entries = await expand_toolset_to_entries(calc_toolset)
        ctx = Context.from_tool_entries(entries, model="test-model")

        assert await ctx.call("add", {"a": 3, "b": 4}) == 7
        assert await ctx.call("multiply", {"a": 3, "b": 4}) == 12

    @pytest.mark.anyio
    async def test_calculator_worker_with_tools(self):
        """Test the full calculator worker with tool calling."""
        from llm_do.ctx_runtime.cli import build_worker_with_toolsets

        worker_path = str(EXAMPLES_NEW_DIR / "calculator" / "main.worker")
        tools_path = str(EXAMPLES_NEW_DIR / "calculator" / "tools.py")

        # Build worker with tools
        worker = await build_worker_with_toolsets(
            worker_path,
            [tools_path],
            model=TestModel(
                call_tools=["factorial"],
                custom_output_text="The factorial of 5 is 120.",
            ),
        )

        assert worker.name == "main"
        assert len(worker.tools) == 4  # factorial, fibonacci, add, multiply

        tool_names = {t.name for t in worker.tools}
        assert tool_names == {"factorial", "fibonacci", "add", "multiply"}


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
        from llm_do.ctx_runtime.cli import build_worker_with_toolsets

        worker_path = str(EXAMPLES_NEW_DIR / "approvals_demo" / "main.worker")

        worker = await build_worker_with_toolsets(
            worker_path,
            [],
            model="anthropic:claude-haiku-4-5",
        )

        assert worker.name == "main"
        # Should have filesystem tools: read_file, write_file, list_files
        assert len(worker.tools) >= 1
        tool_names = {t.name for t in worker.tools}
        assert "write_file" in tool_names or "read_file" in tool_names


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
        from llm_do.ctx_runtime.cli import build_worker_with_toolsets

        worker_path = str(EXAMPLES_NEW_DIR / "code_analyzer" / "main.worker")

        worker = await build_worker_with_toolsets(
            worker_path,
            [],
            model="anthropic:claude-haiku-4-5",
        )

        assert worker.name == "main"
        # Should have shell tool
        assert len(worker.tools) >= 1
        tool_names = {t.name for t in worker.tools}
        assert "shell" in tool_names


class TestExamplesIntegration:
    """Integration tests verifying the full CLI flow."""

    @pytest.mark.anyio
    async def test_build_worker_greeter(self):
        """Test building the greeter worker via CLI helper."""
        from llm_do.ctx_runtime.cli import build_worker_with_toolsets

        worker_path = str(EXAMPLES_NEW_DIR / "greeter" / "main.worker")

        worker = await build_worker_with_toolsets(
            worker_path,
            [],
            model="anthropic:claude-haiku-4-5",
        )

        assert worker.name == "main"
        assert worker.tools == []
        assert "greeter" in worker.instructions.lower()

    @pytest.mark.anyio
    async def test_build_worker_calculator(self):
        """Test building the calculator worker via CLI helper."""
        from llm_do.ctx_runtime.cli import build_worker_with_toolsets

        worker_path = str(EXAMPLES_NEW_DIR / "calculator" / "main.worker")
        tools_path = str(EXAMPLES_NEW_DIR / "calculator" / "tools.py")

        worker = await build_worker_with_toolsets(
            worker_path,
            [tools_path],
            model="anthropic:claude-haiku-4-5",
        )

        assert worker.name == "main"
        assert len(worker.tools) == 4
        assert "calculator" in worker.instructions.lower()
