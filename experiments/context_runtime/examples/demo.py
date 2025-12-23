"""Tiny demo for the context-centric runtime experiment."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic_ai.tools import RunContext, Tool

from tool_calling_model import ToolCallingModel

from src.ctx import Context
from src.entries import ToolEntry, WorkerEntry, tool_entry


# Standard PydanticAI tool signature
async def add_numbers(ctx: RunContext[Context], a: int, b: int) -> dict[str, int]:
    """Add two numbers together."""
    return {"total": a + b}


# Create the tool entry wrapping a PydanticAI Tool
add_tool = ToolEntry(tool=Tool(add_numbers, name="add"))

# Alternative: using the decorator
@tool_entry("multiply")
async def multiply_numbers(ctx: RunContext[Context], x: int, y: int) -> dict[str, int]:
    """Multiply two numbers together."""
    return {"product": x * y}


if __name__ == "__main__":
    model = ToolCallingModel({"tool_calls": [{"name": "add", "args": {"a": 2, "b": 3}}]})
    worker = WorkerEntry(
        name="adder",
        instructions="Add two numbers using the add tool.",
        model=model,
        tools=[add_tool],
    )
    ctx = Context.from_worker(worker)
    result = asyncio.run(ctx.run(worker, {"a": 2, "b": 3}))
    print("Result:", result)
    print("Trace:")
    for t in ctx.trace:
        print(f"  {t.name} ({t.kind}) depth={t.depth} in={t.input_data} out={t.output_data}")
    print("Usage:", ctx.usage)
