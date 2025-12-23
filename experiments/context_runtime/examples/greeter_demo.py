"""Minimal greeter example - just an LLM worker with no tools."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic_ai.models.test import TestModel

from src.ctx import Context
from src.entries import WorkerEntry


if __name__ == "__main__":
    greeter = WorkerEntry(
        name="greeter",
        instructions="Greet the user warmly based on their name.",
        model=TestModel(custom_output_text="Hello Alice! Welcome, it's wonderful to meet you!"),
    )

    ctx = Context.from_worker(greeter)
    result = asyncio.run(ctx.run(greeter, {"name": "Alice"}))

    print("Result:", result)
    print("\nTrace:")
    for t in ctx.trace:
        print(f"  {t.name} ({t.kind}) depth={t.depth}")
