#!/usr/bin/env python
"""Run an LLM worker with tools loaded from Python and/or worker files.

Usage:
    llm-run <worker.worker> [tools.py...] "Your prompt here"
    llm-run <worker.worker> [tools.py...] --entry NAME "Your prompt"
    llm-run <worker.worker> [tools.py...] --all-tools "Your prompt"

Supported file types:
    .py     - Python file with toolsets (auto-discovered via isinstance)
    .worker - Worker definition file (YAML frontmatter + instructions)

Entry point resolution:
    1. If --entry NAME specified, use that entry
    2. Else if "main" entry exists, use it
    3. Else use the first worker loaded

Toolsets:
    - Worker files reference toolsets by name in the toolsets: section
    - Python files export AbstractToolset instances (including FunctionToolset)
    - Built-in toolsets: shell, filesystem
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from pydantic_ai.toolsets import AbstractToolset

from .ctx import Context, ApprovalFn
from .registry import Registry
from .entries import ToolEntry, WorkerEntry, ToolsetToolEntry, WorkerToolset
from .worker_file import load_worker_file
from .discovery import (
    load_toolsets_from_files,
    load_entries_from_files,
    expand_toolset_to_entries,
)
from .builtins import BUILTIN_TOOLSETS, get_builtin_toolset


ENV_MODEL_VAR = "LLM_DO_MODEL"


async def build_entry_worker(
    worker_files: list[str],
    python_files: list[str],
    model: str | None = None,
    entry_name: str = "main",
) -> WorkerEntry:
    """Build the entry worker with all toolsets resolved.

    This function:
    1. Loads all Python toolsets and entries
    2. Creates WorkerToolset wrappers for all .worker files
    3. Resolves toolset references (workers can call other workers)
    4. Returns the entry worker by name

    Args:
        worker_files: List of .worker file paths
        python_files: List of Python file paths containing toolsets
        model: Optional model override for the entry worker
        entry_name: Name of the entry worker (default: "main")

    Returns:
        The entry WorkerEntry with tools populated

    Raises:
        ValueError: If entry not found, name conflict, or unknown toolset
    """
    # Load Python toolsets
    python_toolsets = load_toolsets_from_files(python_files)

    # Load Python entries (for code entry pattern)
    python_entries = load_entries_from_files(python_files)

    if not worker_files and not python_entries:
        raise ValueError("At least one .worker or .py file with entries required")

    # First pass: create stub WorkerToolsets for all workers
    worker_toolsets: dict[str, WorkerToolset] = {}
    worker_paths: dict[str, str] = {}  # name -> path

    for worker_path in worker_files:
        worker_file = load_worker_file(worker_path)
        name = worker_file.name

        # Check for duplicate worker names
        if name in worker_toolsets:
            raise ValueError(f"Duplicate worker name: {name}")

        # Check for conflict with Python entries
        if name in python_entries:
            raise ValueError(f"Worker name '{name}' conflicts with Python entry")

        stub = WorkerEntry(
            name=name,
            instructions=worker_file.instructions,
            model=worker_file.model,
            tools=[],
        )
        worker_toolsets[name] = WorkerToolset(stub)
        worker_paths[name] = worker_path

    # Determine entry source
    if entry_name in worker_toolsets:
        entry_is_worker = True
    elif entry_name in python_entries:
        entry_is_worker = False
    else:
        available = list(worker_toolsets.keys()) + list(python_entries.keys())
        raise ValueError(f"Entry '{entry_name}' not found. Available: {available}")

    # Second pass: build all workers with resolved tools
    workers: dict[str, WorkerEntry] = {}

    for name, worker_path in worker_paths.items():
        worker_file = load_worker_file(worker_path)

        # Available toolsets: Python + other workers (not self)
        available_workers = {k: v for k, v in worker_toolsets.items() if k != name}
        all_toolsets: dict[str, AbstractToolset[Any]] = {}
        all_toolsets.update(python_toolsets)
        all_toolsets.update(available_workers)

        # Resolve and expand toolsets into tool entries
        tools: list[ToolsetToolEntry] = []

        for toolset_name, toolset_config in worker_file.toolsets.items():
            if toolset_name in all_toolsets:
                toolset = all_toolsets[toolset_name]
                tool_entries = await expand_toolset_to_entries(toolset, toolset_config)
                tools.extend(tool_entries)
            elif toolset_name in BUILTIN_TOOLSETS:
                toolset = get_builtin_toolset(toolset_name, toolset_config)
                tool_entries = await expand_toolset_to_entries(toolset, toolset_config)
                tools.extend(tool_entries)
            else:
                available_names = list(all_toolsets.keys()) + list(BUILTIN_TOOLSETS.keys())
                raise ValueError(f"Unknown toolset '{toolset_name}'. Available: {available_names}")

        # Apply model override only to entry worker
        worker_model = model if name == entry_name else worker_file.model

        workers[name] = WorkerEntry(
            name=name,
            instructions=worker_file.instructions,
            model=worker_model,
            tools=tools,
        )

        # Update toolset with fully built worker
        worker_toolsets[name] = WorkerToolset(workers[name])

    if entry_is_worker:
        return workers[entry_name]
    else:
        return python_entries[entry_name]


async def run(
    files: list[str],
    prompt: str,
    model: str | None = None,
    entry_name: str | None = None,
    all_tools: bool = False,
    approve_all: bool = False,
) -> tuple[str, Context]:
    """Load entries and run with the given prompt.

    Args:
        files: List of .py and .worker files
        prompt: User prompt
        model: Optional model override
        entry_name: Optional entry point name (default: "main")
        all_tools: If True, make all entries available to the entry worker
        approve_all: If True, auto-approve all tool calls

    Returns:
        Tuple of (result, context)
    """
    # Separate worker files and Python files
    worker_files = [f for f in files if f.endswith(".worker")]
    python_files = [f for f in files if f.endswith(".py")]

    # Build entry worker
    resolved_entry_name = entry_name or "main"
    entry = await build_entry_worker(worker_files, python_files, model, resolved_entry_name)

    # If --all-tools, give entry access to all discovered toolsets
    if all_tools and isinstance(entry, WorkerEntry):
        existing_names = {t.name for t in entry.tools}
        additional_tools = []
        discovered_toolsets = load_toolsets_from_files(python_files)
        for toolset in discovered_toolsets.values():
            tool_entries = await expand_toolset_to_entries(toolset)
            for tool_entry in tool_entries:
                if tool_entry.name not in existing_names:
                    additional_tools.append(tool_entry)
                    existing_names.add(tool_entry.name)

        entry = WorkerEntry(
            name=entry.name,
            instructions=entry.instructions,
            model=entry.model or model,
            tools=list(entry.tools) + additional_tools,
            schema_in=entry.schema_in,
            schema_out=entry.schema_out,
        )

    # Set up approval function
    approval: ApprovalFn | None = None
    if approve_all:
        approval = lambda entry, input_data: True
    else:
        # In headless mode without --approve-all, deny tools that require approval
        def headless_approval(e: Any, data: Any) -> bool:
            if getattr(e, "requires_approval", False):
                raise PermissionError(
                    f"Tool '{e.name}' requires approval. "
                    f"Use --approve-all to auto-approve all tools in headless mode."
                )
            return True
        approval = headless_approval

    # Create context - for ToolEntry, provide workers as available entries
    available = list(workers.values()) if isinstance(entry, ToolEntry) else None
    ctx = Context.from_entry(entry, model=model, available=available, approval=approval)

    result = await ctx.run(entry, {"input": prompt})

    return result, ctx


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("files", nargs="+", help="Worker (.worker) and Python (.py) files")
    parser.add_argument("prompt", nargs="?", help="Prompt for the LLM")
    parser.add_argument("--entry", "-e", help="Entry point name (default: 'main' or first worker)")
    parser.add_argument("--all-tools", "-a", action="store_true", help="Make all discovered toolsets available")
    parser.add_argument(
        "--model", "-m",
        default=os.environ.get(ENV_MODEL_VAR),
        help=f"Model to use (default: ${ENV_MODEL_VAR} env var)",
    )
    parser.add_argument("--approve-all", action="store_true", help="Auto-approve all tool calls")
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
        parser.error("At least one .worker or .py file required")

    # Combine prompt from positional and any non-file args
    if args.prompt:
        prompt_parts.append(args.prompt)
    prompt = " ".join(prompt_parts) if prompt_parts else None

    # Single prompt mode
    if not prompt:
        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        else:
            parser.error("Prompt required (as argument or via stdin)")

    result, ctx = asyncio.run(run(
        files, prompt, args.model, args.entry, args.all_tools, args.approve_all
    ))
    print(result)

    if args.trace:
        print("\n--- Trace ---", file=sys.stderr)
        for t in ctx.trace:
            print(f"  {t.name} ({t.kind}) depth={t.depth}", file=sys.stderr)


if __name__ == "__main__":
    main()
