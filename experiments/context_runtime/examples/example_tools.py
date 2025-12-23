"""Example tools file for llm_do.py.

This file defines tools that will be auto-discovered and made available to the LLM.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic_ai.tools import RunContext, Tool

from src.ctx import Context
from src.entries import ToolEntry, tool_entry


# Using the decorator
@tool_entry("list_files")
async def list_files(ctx: RunContext[Context], path: str = ".", pattern: str = "*") -> list[str]:
    """List files in a directory matching a pattern."""
    return [str(p) for p in sorted(Path(path).glob(pattern))]


@tool_entry("read_file")
async def read_file(ctx: RunContext[Context], path: str) -> str:
    """Read the contents of a file."""
    return Path(path).read_text(encoding="utf-8")


@tool_entry("write_file")
async def write_file(ctx: RunContext[Context], path: str, content: str) -> str:
    """Write content to a file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} bytes to {path}"


# Using direct ToolEntry construction
async def get_current_dir(ctx: RunContext[Context]) -> str:
    """Get the current working directory."""
    return str(Path.cwd())

current_dir_tool = ToolEntry(tool=Tool(get_current_dir, name="get_current_dir"))
