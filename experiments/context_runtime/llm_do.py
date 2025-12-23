#!/usr/bin/env python
"""Run an LLM with tools/workers loaded from Python and/or worker files.

Usage:
    python llm_do.py <files...> "Your prompt here"
    python llm_do.py <files...> --entry NAME "Your prompt"
    python llm_do.py <files...> --all-tools "Your prompt"
    python llm_do.py <files...> --interactive

Supported file types:
    .py     - Python file with ToolEntry/WorkerEntry definitions (auto-discovered)
    .worker - Worker definition file (YAML frontmatter + instructions)

Entry point resolution:
    1. If --entry NAME specified, use that entry
    2. Else if "main" entry exists, use it
    3. Else error (no entry point found)

The entry worker uses only its defined tools. Use --all-tools to make all
discovered entries available to the entry worker.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

from src.ctx import Context
from src.entries import CallableEntry, ToolEntry, WorkerEntry
from src.worker_file import load_worker_file as load_worker_file_raw


ENV_MODEL_VAR = "LLM_DO_MODEL"


def load_worker_file(path: str) -> WorkerEntry:
    """Load a WorkerEntry from a .worker file."""
    wf = load_worker_file_raw(path)
    return WorkerEntry(
        name=wf.name,
        instructions=wf.instructions,
        model=wf.model,
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


def discover_entries_from_module(module: ModuleType) -> list[CallableEntry]:
    """Discover ToolEntry and WorkerEntry instances from a module."""
    entries = []
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, (ToolEntry, WorkerEntry)):
            entries.append(obj)
    return entries


# --- Entry loading from multiple files ---

def load_entries(files: list[str]) -> dict[str, CallableEntry]:
    """Load entries from multiple files into a name->entry dict."""
    entries: dict[str, CallableEntry] = {}

    for file_path in files:
        path = Path(file_path)
        if path.suffix == ".worker":
            worker = load_worker_file(file_path)
            entries[worker.name] = worker
        else:
            module = load_module(file_path)
            for entry in discover_entries_from_module(module):
                entries[entry.name] = entry

    return entries


# --- Orchestrator building ---

def build_orchestrator(entries: list[CallableEntry], model: str) -> WorkerEntry:
    """Build an orchestrator worker that has access to all provided entries."""
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


# --- Main execution ---

async def run(
    files: list[str],
    prompt: str,
    model: str | None = None,
    entry_name: str | None = None,
    all_tools: bool = False,
) -> tuple[str, Context]:
    """Load entries and run with the given prompt."""
    all_entries = load_entries(files)

    if not all_entries:
        raise ValueError(f"No entries found in {files}")

    # Determine entry point
    if entry_name:
        if entry_name not in all_entries:
            raise ValueError(f"Entry '{entry_name}' not found. Available: {list(all_entries.keys())}")
        entry = all_entries[entry_name]
    elif "main" in all_entries:
        entry = all_entries["main"]
        entry_name = "main"
    else:
        raise ValueError(f"No 'main' entry found. Use --entry to specify. Available: {list(all_entries.keys())}")

    # If --all-tools, give entry access to all other entries
    if all_tools and isinstance(entry, WorkerEntry):
        other_entries = [e for name, e in all_entries.items() if name != entry_name]
        entry = WorkerEntry(
            name=entry.name,
            instructions=entry.instructions,
            model=entry.model or model,
            tools=list(entry.tools) + other_entries,
            schema_in=entry.schema_in,
            schema_out=entry.schema_out,
        )

    # Resolve model: entry's model, CLI arg, or env var
    if isinstance(entry, WorkerEntry) and entry.model is None:
        if model is None:
            raise ValueError(
                f"No model specified. Set {ENV_MODEL_VAR} environment variable, "
                f"use --model flag, or define model in the worker."
            )
        entry.model = model

    ctx = Context.from_worker(entry)
    result = await ctx.run(entry, {"input": prompt})

    return result, ctx


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("files", nargs="+", help="Python (.py) and/or worker (.worker) files")
    parser.add_argument("prompt", nargs="?", help="Prompt for the LLM")
    parser.add_argument("--entry", "-e", help="Entry point name (default: 'main' if exists)")
    parser.add_argument("--all-tools", "-a", action="store_true", help="Make all discovered entries available as tools")
    parser.add_argument(
        "--model", "-m",
        default=os.environ.get(ENV_MODEL_VAR),
        help=f"Model to use (default: ${ENV_MODEL_VAR} env var)",
    )
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--trace", action="store_true", help="Show execution trace")

    args = parser.parse_args()

    # Separate files from prompt in the files list (prompt might be mixed in)
    files = []
    prompt_parts = []
    for arg in args.files:
        if Path(arg).suffix in (".py", ".worker") and Path(arg).exists():
            files.append(arg)
        else:
            prompt_parts.append(arg)

    if not files:
        parser.error("At least one .py or .worker file required")

    # Combine prompt from positional and any non-file args
    if args.prompt:
        prompt_parts.append(args.prompt)
    prompt = " ".join(prompt_parts) if prompt_parts else None

    if args.interactive:
        # Interactive REPL mode
        all_entries = load_entries(files)
        print(f"Loaded {len(all_entries)} entries:")
        for name, e in all_entries.items():
            print(f"  - {name} ({e.kind})")

        print("\nEnter prompts (Ctrl+D to exit):")
        try:
            while True:
                user_input = input("\n> ")
                if not user_input.strip():
                    continue
                result, ctx = asyncio.run(run(
                    files, user_input, args.model, args.entry, args.all_tools
                ))
                print(f"\n{result}")
                if args.trace:
                    print("\n--- Trace ---", file=sys.stderr)
                    for t in ctx.trace:
                        print(f"  {t.name} ({t.kind}) depth={t.depth}", file=sys.stderr)
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
    else:
        # Single prompt mode
        if not prompt:
            if not sys.stdin.isatty():
                prompt = sys.stdin.read().strip()
            else:
                parser.error("Prompt required (as argument or via stdin)")

        result, ctx = asyncio.run(run(files, prompt, args.model, args.entry, args.all_tools))
        print(result)

        if args.trace:
            print("\n--- Trace ---", file=sys.stderr)
            for t in ctx.trace:
                print(f"  {t.name} ({t.kind}) depth={t.depth}", file=sys.stderr)


if __name__ == "__main__":
    main()
