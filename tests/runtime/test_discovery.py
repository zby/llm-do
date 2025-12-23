"""Tests for module loading and discovery."""
import pytest
import tempfile
import os
from pathlib import Path

from llm_do.ctx_runtime import (
    load_module,
    discover_toolsets_from_module,
    discover_entries_from_module,
    expand_toolset_to_entries,
    load_toolsets_from_files,
)


class TestLoadModule:
    """Tests for load_module function."""

    def test_load_simple_module(self):
        """Test loading a simple Python module."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("VALUE = 42\n")
            f.flush()

            try:
                module = load_module(f.name)
                assert module.VALUE == 42
            finally:
                os.unlink(f.name)

    def test_load_nonexistent_raises(self):
        """Test that loading nonexistent file raises an error."""
        with pytest.raises((ImportError, FileNotFoundError)):
            load_module("/nonexistent/path/module.py")


class TestDiscoverToolsets:
    """Tests for toolset discovery."""

    def test_discover_function_toolset(self):
        """Test discovering FunctionToolset from module."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""\
from pydantic_ai.toolsets import FunctionToolset

my_tools = FunctionToolset()

@my_tools.tool
def add(a: int, b: int) -> int:
    return a + b
""")
            f.flush()

            try:
                module = load_module(f.name)
                toolsets = discover_toolsets_from_module(module)

                assert "my_tools" in toolsets
                # Check it's a FunctionToolset
                from pydantic_ai.toolsets import FunctionToolset
                assert isinstance(toolsets["my_tools"], FunctionToolset)
            finally:
                os.unlink(f.name)

    def test_discover_skips_private(self):
        """Test that private attributes are skipped."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""\
from pydantic_ai.toolsets import FunctionToolset

_private_tools = FunctionToolset()
public_tools = FunctionToolset()
""")
            f.flush()

            try:
                module = load_module(f.name)
                toolsets = discover_toolsets_from_module(module)

                assert "_private_tools" not in toolsets
                assert "public_tools" in toolsets
            finally:
                os.unlink(f.name)


class TestExpandToolset:
    """Tests for expand_toolset_to_entries."""

    @pytest.mark.anyio
    async def test_expand_function_toolset(self):
        """Test expanding a FunctionToolset into entries."""
        from pydantic_ai.toolsets import FunctionToolset

        toolset = FunctionToolset()

        @toolset.tool
        def multiply(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b

        @toolset.tool
        def divide(a: int, b: int) -> float:
            """Divide two numbers."""
            return a / b

        entries = await expand_toolset_to_entries(toolset)

        assert len(entries) == 2
        names = {e.name for e in entries}
        assert names == {"multiply", "divide"}

        # Check entry properties
        for entry in entries:
            assert entry.kind == "tool"
            assert entry.toolset is toolset


class TestLoadToolsetsFromFiles:
    """Tests for load_toolsets_from_files."""

    def test_load_from_multiple_files(self):
        """Test loading toolsets from multiple files."""
        files = []
        try:
            # Create first file
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
                f.write("""\
from pydantic_ai.toolsets import FunctionToolset

math_tools = FunctionToolset()

@math_tools.tool
def add(a: int, b: int) -> int:
    return a + b
""")
                files.append(f.name)

            # Create second file
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
                f.write("""\
from pydantic_ai.toolsets import FunctionToolset

string_tools = FunctionToolset()

@string_tools.tool
def upper(s: str) -> str:
    return s.upper()
""")
                files.append(f.name)

            toolsets = load_toolsets_from_files(files)

            assert "math_tools" in toolsets
            assert "string_tools" in toolsets

        finally:
            for fname in files:
                os.unlink(fname)

    def test_duplicate_name_raises(self):
        """Test that duplicate toolset names raise ValueError."""
        files = []
        try:
            # Create two files with same toolset name
            for _ in range(2):
                with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
                    f.write("""\
from pydantic_ai.toolsets import FunctionToolset
duplicate_tools = FunctionToolset()
""")
                    files.append(f.name)

            with pytest.raises(ValueError, match="Duplicate toolset name"):
                load_toolsets_from_files(files)

        finally:
            for fname in files:
                os.unlink(fname)

    def test_skips_non_python_files(self):
        """Test that non-.py files are skipped."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("not python")
            f.flush()

            try:
                toolsets = load_toolsets_from_files([f.name])
                assert toolsets == {}
            finally:
                os.unlink(f.name)
