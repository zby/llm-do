"""File tools with a main entry point.

When loaded with llm_do.py, the "main" worker is used as the entry point
and has access to all the tools defined here.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic_ai.tools import RunContext, Tool

from src.ctx import Context
from src.entries import ToolEntry, WorkerEntry, tool_entry


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


# Main entry point - automatically used when running: llm_do.py file_tools.py "prompt"
main = WorkerEntry(
    name="main",
    instructions="""\
You are a helpful file assistant. You can list, read, and write files.

When the user asks about files:
1. Use list_files to find files
2. Use read_file to read contents
3. Use write_file to create or modify files

Be concise and helpful.
""",
    tools=[list_files, read_file, write_file],  # explicit tool list
)
