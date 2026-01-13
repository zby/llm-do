"""Tests for module loading and discovery."""
import os
import tempfile

import pytest

from llm_do.runtime import (
    discover_toolsets_from_module,
    load_module,
    load_toolsets_from_files,
    load_workers_from_files,
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
        """Test discovering ToolsetSpec from module."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""\
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import ToolsetSpec

def build_tools(_ctx):
    tools = FunctionToolset()

    @tools.tool
    def add(a: int, b: int) -> int:
        return a + b

    return tools

my_tools = ToolsetSpec(factory=build_tools)
""")
            f.flush()

            try:
                module = load_module(f.name)
                toolsets = discover_toolsets_from_module(module)

                assert "my_tools" in toolsets
                from llm_do.runtime import ToolsetSpec
                assert isinstance(toolsets["my_tools"], ToolsetSpec)
            finally:
                os.unlink(f.name)

    def test_discover_skips_private(self):
        """Test that private attributes are skipped."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""\
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import ToolsetSpec

def build_private(_ctx):
    return FunctionToolset()

def build_public(_ctx):
    return FunctionToolset()

_private_tools = ToolsetSpec(factory=build_private)
public_tools = ToolsetSpec(factory=build_public)
""")
            f.flush()

            try:
                module = load_module(f.name)
                toolsets = discover_toolsets_from_module(module)

                assert "_private_tools" not in toolsets
                assert "public_tools" in toolsets
            finally:
                os.unlink(f.name)


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
from llm_do.runtime import ToolsetSpec

def build_math(_ctx):
    tools = FunctionToolset()

    @tools.tool
    def add(a: int, b: int) -> int:
        return a + b

    return tools

math_tools = ToolsetSpec(factory=build_math)
""")
                files.append(f.name)

            # Create second file
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
                f.write("""\
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import ToolsetSpec

def build_string(_ctx):
    tools = FunctionToolset()

    @tools.tool
    def upper(s: str) -> str:
        return s.upper()

    return tools

string_tools = ToolsetSpec(factory=build_string)
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
from llm_do.runtime import ToolsetSpec

def build_tools(_ctx):
    return FunctionToolset()

duplicate_tools = ToolsetSpec(factory=build_tools)
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


class TestLoadWorkersFromFiles:
    """Tests for load_workers_from_files."""

    def test_duplicate_worker_name_in_file_raises(self):
        """Test duplicate Worker names in a single file."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""\
from llm_do.runtime import Worker

worker_one = Worker(name="dup", instructions="first")
worker_two = Worker(name="dup", instructions="second")
""")
            f.flush()

            try:
                with pytest.raises(ValueError, match="Duplicate worker name"):
                    load_workers_from_files([f.name])
            finally:
                os.unlink(f.name)

    def test_duplicate_worker_name_across_files_raises(self):
        """Test duplicate Worker names across multiple files."""
        files = []
        try:
            for label in ("one", "two"):
                with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
                    f.write(f"""\
from llm_do.runtime import Worker

worker_{label} = Worker(name="dup", instructions="{label}")
""")
                    files.append(f.name)

            with pytest.raises(ValueError, match="Duplicate worker name"):
                load_workers_from_files(files)
        finally:
            for fname in files:
                os.unlink(fname)
