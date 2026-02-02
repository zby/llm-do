"""Tests for module loading and discovery."""
import os
import tempfile

import pytest

from llm_do.runtime import (
    discover_tools_from_module,
    discover_toolsets_from_module,
    load_agents_from_files,
    load_module,
    load_tools_from_files,
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

    def test_discover_toolsets_from_registry(self):
        """Discover toolsets via TOOLSETS registry."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""\
from pydantic_ai.toolsets import FunctionToolset


def build_tools(_ctx):
    tools = FunctionToolset()

    @tools.tool
    def add(a: int, b: int) -> int:
        return a + b

    return tools

TOOLSETS = {"my_tools": build_tools}
""")
            f.flush()

            try:
                module = load_module(f.name)
                toolsets = discover_toolsets_from_module(module)

                assert "my_tools" in toolsets
            finally:
                os.unlink(f.name)

    def test_discover_toolsets_skips_private_instances(self):
        """Private toolset instances are ignored."""
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


class TestDiscoverTools:
    """Tests for tool discovery."""

    def test_discover_tools_from_tools_list(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""\
def add(a: int, b: int) -> int:
    return a + b

TOOLS = [add]
""")
            f.flush()

            try:
                module = load_module(f.name)
                tools = discover_tools_from_module(module)

                assert "add" in tools
            finally:
                os.unlink(f.name)

    def test_discover_tools_from_all(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""\
from pydantic_ai import Tool


def hello(name: str) -> str:
    return name

hello_tool = Tool(hello, name="hello_tool")
__all__ = ["hello_tool"]
""")
            f.flush()

            try:
                module = load_module(f.name)
                tools = discover_tools_from_module(module)

                assert "hello_tool" in tools
            finally:
                os.unlink(f.name)

    def test_tools_registry_rejects_toolsets(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""\
from pydantic_ai.toolsets import FunctionToolset

TOOLS = [FunctionToolset()]
""")
            f.flush()

            try:
                module = load_module(f.name)
                with pytest.raises(ValueError, match="Invalid tools registry"):
                    discover_tools_from_module(module)
            finally:
                os.unlink(f.name)

    def test_toolsets_registry_rejects_tools(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""\
from pydantic_ai import Tool

def ping() -> str:
    return "pong"

TOOLSETS = {"oops": Tool(ping, name="oops")}
""")
            f.flush()

            try:
                module = load_module(f.name)
                with pytest.raises(ValueError, match="Invalid toolsets registry"):
                    discover_toolsets_from_module(module)
            finally:
                os.unlink(f.name)


class TestLoadToolsetsFromFiles:
    """Tests for load_toolsets_from_files."""

    def test_load_from_multiple_files(self):
        """Test loading toolsets from multiple files."""
        files = []
        try:
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
                f.write("""\
from pydantic_ai.toolsets import FunctionToolset


def build_math(_ctx):
    tools = FunctionToolset()

    @tools.tool
    def add(a: int, b: int) -> int:
        return a + b

    return tools

TOOLSETS = {"math_tools": build_math}
""")
                files.append(f.name)

            with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
                f.write("""\
from pydantic_ai.toolsets import FunctionToolset


def build_string(_ctx):
    tools = FunctionToolset()

    @tools.tool
    def upper(s: str) -> str:
        return s.upper()

    return tools

TOOLSETS = {"string_tools": build_string}
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
            for _ in range(2):
                with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
                    f.write("""\
from pydantic_ai.toolsets import FunctionToolset


def build_tools(_ctx):
    return FunctionToolset()

TOOLSETS = {"duplicate_tools": build_tools}
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


class TestLoadToolsFromFiles:
    """Tests for load_tools_from_files."""

    def test_duplicate_name_raises(self):
        files = []
        try:
            for _ in range(2):
                with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
                    f.write("""\

def ping() -> str:
    return "pong"

TOOLS = [ping]
""")
                    files.append(f.name)

            with pytest.raises(ValueError, match="Duplicate tool name"):
                load_tools_from_files(files)
        finally:
            for fname in files:
                os.unlink(fname)


class TestLoadAgentsFromFiles:
    """Tests for load_agents_from_files."""

    def test_duplicate_agent_name_in_file_raises(self):
        """Test duplicate AgentSpec names in a single file."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""\
from pydantic_ai.models.test import TestModel
from llm_do.runtime import AgentSpec

a1 = AgentSpec(name="dup", instructions="first", model=TestModel())
a2 = AgentSpec(name="dup", instructions="second", model=TestModel())
""")
            f.flush()

            try:
                with pytest.raises(ValueError, match="Duplicate agent name"):
                    load_agents_from_files([f.name])
            finally:
                os.unlink(f.name)

    def test_duplicate_agent_name_across_files_raises(self):
        """Test duplicate AgentSpec names across multiple files."""
        files = []
        try:
            for label in ("one", "two"):
                with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
                    f.write(f"""\
from pydantic_ai.models.test import TestModel
from llm_do.runtime import AgentSpec

agent_{label} = AgentSpec(name="dup", instructions="{label}", model=TestModel())
""")
                    files.append(f.name)

            with pytest.raises(ValueError, match="Duplicate agent name"):
                load_agents_from_files(files)
        finally:
            for fname in files:
                os.unlink(fname)
