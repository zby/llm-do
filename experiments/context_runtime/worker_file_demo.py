"""Run a worker from a .worker file definition.

Worker file format:
---
name: worker_name
description: Optional description
model: optional model override (e.g., anthropic:claude-haiku)
---

Instructions/system prompt in markdown.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext, Tool

from ctx import Context, ModelType
from entries import ToolEntry, WorkerEntry


@dataclass
class WorkerFile:
    """Parsed worker file."""
    name: str
    description: str | None
    instructions: str
    model: str | None = None


def parse_worker_file(content: str) -> WorkerFile:
    """Parse a worker file with YAML frontmatter and markdown instructions."""
    # Match YAML frontmatter between --- markers
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        raise ValueError("Invalid worker file format: missing frontmatter")

    frontmatter_str, instructions = match.groups()
    frontmatter = yaml.safe_load(frontmatter_str)

    if not isinstance(frontmatter, dict):
        raise ValueError("Invalid frontmatter: expected YAML mapping")

    name = frontmatter.get("name")
    if not name:
        raise ValueError("Worker file must have a 'name' field")

    return WorkerFile(
        name=name,
        description=frontmatter.get("description"),
        instructions=instructions.strip(),
        model=frontmatter.get("model"),
    )


def load_worker_file(path: str | Path) -> WorkerFile:
    """Load and parse a worker file from disk."""
    content = Path(path).read_text(encoding="utf-8")
    return parse_worker_file(content)


async def run_worker(
    ctx: RunContext[Context],
    worker_path: str,
    input_text: str
) -> str:
    """Load a worker file and run it with the given input.

    Args:
        worker_path: Path to the .worker file
        input_text: User input to send to the worker

    Returns:
        The worker's response
    """
    worker_file = load_worker_file(worker_path)

    # Create WorkerEntry from file
    worker = WorkerEntry(
        name=worker_file.name,
        instructions=worker_file.instructions,
        model=worker_file.model,  # None means use ctx default
    )

    # Register and call via context
    ctx.deps.registry.register(worker)
    return await ctx.deps.call(worker_file.name, {"input": input_text})


# Example worker file content
EXAMPLE_WORKER = """\
---
name: greeter
description: A friendly assistant that greets users and responds to messages
---

You are a friendly and helpful assistant.

When the user provides a message:
1. Greet them warmly
2. Respond thoughtfully to their message
3. Be concise but friendly

Keep your responses brief and conversational.
"""


if __name__ == "__main__":
    # Write example worker file
    worker_path = Path(__file__).parent / "greeter.worker"
    worker_path.write_text(EXAMPLE_WORKER, encoding="utf-8")
    print(f"Created: {worker_path}")

    # Parse and display
    worker_file = load_worker_file(worker_path)
    print(f"\nParsed worker:")
    print(f"  name: {worker_file.name}")
    print(f"  description: {worker_file.description}")
    print(f"  model: {worker_file.model}")
    print(f"  instructions: {worker_file.instructions[:50]}...")

    # Create the run_worker tool
    run_worker_tool = ToolEntry(tool=Tool(run_worker, name="run_worker"))

    # Create context with a default model
    ctx = Context.from_tool_entries(
        [run_worker_tool],
        model=TestModel(custom_output_text="Hello! It's great to meet you. How can I help today?"),
    )

    # Run the worker via the tool
    result = asyncio.run(ctx.call("run_worker", {
        "worker_path": str(worker_path),
        "input_text": "Hi, my name is Bob!",
    }))

    print(f"\nResult: {result}")
    print("\nTrace:")
    for t in ctx.trace:
        print(f"  {t.name} ({t.kind}) depth={t.depth}")
