#!/usr/bin/env python
"""Run a worker from a .worker file.

Usage:
    python run_worker.py <worker_file> [input_text]
    echo "Hello" | python run_worker.py <worker_file>

Worker file format:
---
name: worker_name
description: Optional description
model: anthropic:claude-haiku  # optional, defaults to anthropic:claude-haiku
---

Instructions/system prompt in markdown.
"""
from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from ctx import Context
from entries import WorkerEntry


DEFAULT_MODEL = "anthropic:claude-haiku-4-5"


@dataclass
class WorkerFile:
    """Parsed worker file."""
    name: str
    description: str | None
    instructions: str
    model: str | None = None


def parse_worker_file(content: str) -> WorkerFile:
    """Parse a worker file with YAML frontmatter and markdown instructions."""
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


async def run(worker_path: str, input_text: str) -> str:
    """Load and run a worker file."""
    worker_file = load_worker_file(worker_path)

    model = worker_file.model or DEFAULT_MODEL

    worker = WorkerEntry(
        name=worker_file.name,
        instructions=worker_file.instructions,
        model=model,
    )

    ctx = Context.from_worker(worker)
    return await ctx.call(worker_file.name, {"input": input_text})


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    worker_path = sys.argv[1]

    # Get input from argument or stdin
    if len(sys.argv) >= 3:
        input_text = " ".join(sys.argv[2:])
    elif not sys.stdin.isatty():
        input_text = sys.stdin.read().strip()
    else:
        input_text = input("Enter message: ")

    result = asyncio.run(run(worker_path, input_text))
    print(result)


if __name__ == "__main__":
    main()
