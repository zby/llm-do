#!/usr/bin/env python
"""Run an LLM with tools/workers loaded from a Python or worker file.

Usage:
    python llm_do.py <file> "Your prompt here"
    python llm_do.py <file> --interactive
    echo "Your prompt" | python llm_do.py <file>

Supported file types:
    .py     - Python file with ToolEntry/WorkerEntry definitions (auto-discovered)
    .worker - Worker definition file (YAML frontmatter + instructions)
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import yaml

from ctx import Context
from entries import CallableEntry, ToolEntry, WorkerEntry


DEFAULT_MODEL = "anthropic:claude-haiku-4-5"


# --- Worker file parsing ---

def parse_worker_file(content: str) -> dict:
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

    return {
        "name": name,
        "description": frontmatter.get("description"),
        "instructions": instructions.strip(),
        "model": frontmatter.get("model"),
    }


def load_worker_file(path: str) -> WorkerEntry:
    """Load a WorkerEntry from a .worker file."""
    content = Path(path).read_text(encoding="utf-8")
    parsed = parse_worker_file(content)
    return WorkerEntry(
        name=parsed["name"],
        instructions=parsed["instructions"],
        model=parsed["model"],
    )


# --- Python module loading ---

def load_module(path: str) -> ModuleType:
    """Load a Python module from a file path."""
    path = Path(path).resolve()
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def discover_entries(module: ModuleType) -> list[CallableEntry]:
    """Discover ToolEntry and WorkerEntry instances from a module."""
    entries = []
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, (ToolEntry, WorkerEntry)):
            entries.append(obj)
    return entries


def build_orchestrator(entries: list[CallableEntry], model: str) -> WorkerEntry:
    """Build an orchestrator worker that has access to all discovered entries."""
    tool_descriptions = []
    for entry in entries:
        if isinstance(entry, ToolEntry):
            desc = entry.tool.description or "No description"
            tool_descriptions.append(f"- {entry.name}: {desc}")
        elif isinstance(entry, WorkerEntry):
            tool_descriptions.append(f"- {entry.name}: {entry.instructions[:100]}...")

    tools_list = "\n".join(tool_descriptions) if tool_descriptions else "No tools available."

    instructions = f"""\
You are a helpful assistant with access to the following tools:

{tools_list}

Use these tools to help the user accomplish their task. Think step by step and use tools as needed.
"""

    return WorkerEntry(
        name="orchestrator",
        instructions=instructions,
        model=model,
        tools=entries,
    )


async def run(file_path: str, prompt: str, model: str) -> str:
    """Load tools/worker and run with the given prompt."""
    path = Path(file_path)

    if path.suffix == ".worker":
        # Simple worker file - run directly
        worker = load_worker_file(file_path)
        if worker.model is None:
            worker.model = model
        ctx = Context.from_worker(worker)
        result = await ctx.call(worker.name, {"input": prompt})
    else:
        # Python file - discover tools and build orchestrator
        module = load_module(file_path)
        entries = discover_entries(module)

        if not entries:
            print(f"Warning: No ToolEntry or WorkerEntry found in {file_path}", file=sys.stderr)

        orchestrator = build_orchestrator(entries, model)
        ctx = Context.from_worker(orchestrator)
        result = await ctx.call("orchestrator", {"input": prompt})

    # Print trace summary
    print("\n--- Trace ---", file=sys.stderr)
    for t in ctx.trace:
        print(f"  {t.name} ({t.kind}) depth={t.depth}", file=sys.stderr)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", help="Python (.py) or worker (.worker) file")
    parser.add_argument("prompt", nargs="?", help="Prompt for the LLM")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")

    args = parser.parse_args()
    path = Path(args.file)

    if args.interactive:
        # Interactive REPL mode
        if path.suffix == ".worker":
            worker = load_worker_file(args.file)
            if worker.model is None:
                worker.model = args.model
            ctx = Context.from_worker(worker)
            worker_name = worker.name
            print(f"Loaded worker: {worker.name}")
        else:
            module = load_module(args.file)
            entries = discover_entries(module)
            print(f"Loaded {len(entries)} entries from {args.file}")
            for e in entries:
                print(f"  - {e.name} ({e.kind})")
            orchestrator = build_orchestrator(entries, args.model)
            ctx = Context.from_worker(orchestrator)
            worker_name = "orchestrator"

        print("\nEnter prompts (Ctrl+D to exit):")
        try:
            while True:
                prompt = input("\n> ")
                if not prompt.strip():
                    continue
                result = asyncio.run(ctx.call(worker_name, {"input": prompt}))
                print(f"\n{result}")
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
    else:
        # Single prompt mode
        if args.prompt:
            prompt = args.prompt
        elif not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        else:
            parser.error("Prompt required (as argument or via stdin)")

        result = asyncio.run(run(args.file, prompt, args.model))
        print(result)


if __name__ == "__main__":
    main()
