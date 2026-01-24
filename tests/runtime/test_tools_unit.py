"""Unit tests for tool functions.

These tests verify that individual tool functions work correctly,
independent of the LLM/worker infrastructure.
"""
from pathlib import Path

import pytest

from llm_do.runtime import ToolsetBuildContext, load_toolsets_from_files
from tests.runtime.helpers import build_call_scope

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


def _build_toolset(spec):
    return spec.factory(ToolsetBuildContext(worker_name="test"))


class TestCalculatorTools:
    """Unit tests for calculator example tools."""

    @pytest.fixture
    def calc_toolset(self):
        """Load calculator toolset."""
        toolsets = load_toolsets_from_files([EXAMPLES_DIR / "calculator" / "tools.py"])
        return _build_toolset(toolsets["calc_tools"])

    @pytest.fixture
    def ctx(self, calc_toolset):
        """Create scope with calculator toolset."""
        return build_call_scope(toolsets=[calc_toolset], model="test")

    @pytest.mark.anyio
    async def test_add(self, ctx):
        assert await ctx.call_tool("add", {"a": 3, "b": 4}) == 7
        assert await ctx.call_tool("add", {"a": -5, "b": 5}) == 0
        assert await ctx.call_tool("add", {"a": 0, "b": 0}) == 0

    @pytest.mark.anyio
    async def test_multiply(self, ctx):
        assert await ctx.call_tool("multiply", {"a": 3, "b": 4}) == 12
        assert await ctx.call_tool("multiply", {"a": -2, "b": 3}) == -6
        assert await ctx.call_tool("multiply", {"a": 0, "b": 100}) == 0

    @pytest.mark.anyio
    async def test_factorial(self, ctx):
        assert await ctx.call_tool("factorial", {"n": 0}) == 1
        assert await ctx.call_tool("factorial", {"n": 1}) == 1
        assert await ctx.call_tool("factorial", {"n": 5}) == 120
        assert await ctx.call_tool("factorial", {"n": 7}) == 5040

    @pytest.mark.anyio
    async def test_fibonacci(self, ctx):
        # Fibonacci: 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55
        assert await ctx.call_tool("fibonacci", {"n": 0}) == 0
        assert await ctx.call_tool("fibonacci", {"n": 1}) == 1
        assert await ctx.call_tool("fibonacci", {"n": 2}) == 1
        assert await ctx.call_tool("fibonacci", {"n": 10}) == 55


class TestPitchdeckStabilizedTools:
    """Unit tests for pitchdeck_eval_stabilized tools."""

    @pytest.fixture
    def pitchdeck_toolset(self):
        """Load pitchdeck toolset."""
        toolsets = load_toolsets_from_files([EXAMPLES_DIR / "pitchdeck_eval_stabilized" / "tools.py"])
        return _build_toolset(toolsets["pitchdeck_tools"])

    @pytest.fixture
    def ctx(self, pitchdeck_toolset):
        """Create scope with pitchdeck toolset."""
        return build_call_scope(toolsets=[pitchdeck_toolset], model="test")

    @pytest.mark.anyio
    async def test_list_pitchdecks(self, ctx, tmp_path):
        """Test list_pitchdecks with a temp directory."""
        # Create test PDF files
        (tmp_path / "test-deck.pdf").write_bytes(b"fake pdf")
        (tmp_path / "another_deck.pdf").write_bytes(b"fake pdf 2")
        (tmp_path / "not-a-pdf.txt").write_text("ignored")

        result = await ctx.call_tool("list_pitchdecks", {"path": str(tmp_path)})

        assert len(result) == 2
        slugs = {item["slug"] for item in result}
        assert "test-deck" in slugs
        assert "another-deck" in slugs

        # Check output paths are generated
        for item in result:
            assert item["output_path"].startswith("evaluations/")
            assert item["output_path"].endswith(".md")
