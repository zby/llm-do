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
from .entries import ToolEntry, WorkerEntry, ToolsetToolEntry
from .worker_file import load_worker_file
from .discovery import (
    load_toolsets_from_files,
    load_entries_from_files,
    expand_toolset_to_entries,
    discover_worker_files,
)
from .builtins import BUILTIN_TOOLSETS, get_builtin_toolset


ENV_MODEL_VAR = "LLM_DO_MODEL"


async def build_worker_with_toolsets(
    worker_path: str,
    python_files: list[str],
    model: str | None = None,
    _loaded_workers: dict[str, WorkerEntry] | None = None,
) -> WorkerEntry:
    """Build a WorkerEntry with tools loaded from toolsets.

    Toolsets can be:
    - Python AbstractToolset instances from python_files
    - Built-in toolsets (shell, filesystem)
    - Other .worker files in the same directory (workers as toolsets)

    Args:
        worker_path: Path to .worker file
        python_files: List of paths to Python files containing toolsets
        model: Optional model override
        _loaded_workers: Internal cache to prevent circular references

    Returns:
        WorkerEntry with tools populated from toolsets
    """
    # Prevent circular references
    if _loaded_workers is None:
        _loaded_workers = {}

    worker_path_resolved = str(Path(worker_path).resolve())
    if worker_path_resolved in _loaded_workers:
        return _loaded_workers[worker_path_resolved]

    # Load worker file
    worker_file = load_worker_file(worker_path)
    worker_dir = Path(worker_path).parent

    # Load toolsets from Python files
    discovered_toolsets = load_toolsets_from_files(python_files)

    # Discover other .worker files in the same directory (workers as toolsets)
    discovered_workers = discover_worker_files(worker_dir)
    # Don't include self
    discovered_workers.pop(worker_file.name, None)

    # Resolve and expand toolsets into tool entries
    tools: list[ToolsetToolEntry | WorkerEntry] = []

    for toolset_name, toolset_config in worker_file.toolsets.items():
        # Check if it's a worker (workers as toolsets)
        if toolset_name in discovered_workers:
            worker_entry = await build_worker_with_toolsets(
                str(discovered_workers[toolset_name]),
                python_files,
                model=None,  # Use worker's own model
                _loaded_workers=_loaded_workers,
            )
            tools.append(worker_entry)
            continue

        # Check if it's a Python toolset
        if toolset_name in discovered_toolsets:
            toolset = discovered_toolsets[toolset_name]
            tool_entries = await expand_toolset_to_entries(toolset, toolset_config)
            tools.extend(tool_entries)
            continue

        # Check if it's a built-in toolset
        if toolset_name in BUILTIN_TOOLSETS:
            toolset = get_builtin_toolset(toolset_name, toolset_config)
            tool_entries = await expand_toolset_to_entries(toolset, toolset_config)
            tools.extend(tool_entries)
            continue

        # Unknown toolset
        available = (
            list(discovered_toolsets.keys()) +
            list(BUILTIN_TOOLSETS.keys()) +
            list(discovered_workers.keys())
        )
        raise ValueError(
            f"Unknown toolset '{toolset_name}'. "
            f"Available: {available}"
        )

    # Create WorkerEntry
    worker = WorkerEntry(
        name=worker_file.name,
        instructions=worker_file.instructions,
        model=model or worker_file.model,
        tools=tools,
    )

    # Cache to prevent circular references
    _loaded_workers[worker_path_resolved] = worker

    return worker


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
        entry_name: Optional entry point name
        all_tools: If True, make all entries available to the entry worker
        approve_all: If True, auto-approve all tool calls

    Returns:
        Tuple of (result, context)
    """
    # Separate worker files and Python files
    worker_files = [f for f in files if f.endswith(".worker")]
    python_files = [f for f in files if f.endswith(".py")]

    # Load entries from Python files
    all_entries = load_entries_from_files(python_files)

    if not worker_files and not all_entries:
        raise ValueError("At least one .worker or .py file with entries required")

    # Build workers with their toolsets
    workers: dict[str, WorkerEntry] = {}
    for worker_path in worker_files:
        worker = await build_worker_with_toolsets(worker_path, python_files, model)
        workers[worker.name] = worker

    # Determine entry point (workers take precedence, then tool entries)
    if entry_name:
        if entry_name not in workers and entry_name not in all_entries:
            available = list(workers.keys()) + list(all_entries.keys())
            raise ValueError(f"Entry '{entry_name}' not found. Available: {available}")
        entry = workers.get(entry_name) or all_entries.get(entry_name)
    elif "main" in workers:
        entry = workers["main"]
        entry_name = "main"
    elif "main" in all_entries:
        # Support "main" as a tool entry point (code entry pattern)
        entry = all_entries["main"]
        entry_name = "main"
    elif workers:
        entry_name, entry = next(iter(workers.items()))
    elif all_entries:
        # Use first tool entry if no workers
        entry_name, entry = next(iter(all_entries.items()))
    else:
        raise ValueError("No entry point found. Provide a .worker file or .py file with entries.")

    # If --all-tools, give entry access to all discovered toolsets
    if all_tools and isinstance(entry, WorkerEntry):
        # Collect all tools from all toolsets, deduping by name
        existing_names = {t.name for t in entry.tools}
        additional_tools = []
        discovered_toolsets = load_toolsets_from_files(python_files)
        for toolset in discovered_toolsets.values():
            tool_entries = await expand_toolset_to_entries(toolset)
            for tool_entry in tool_entries:
                if tool_entry.name not in existing_names:
                    additional_tools.append(tool_entry)
                    existing_names.add(tool_entry.name)

        # Add to worker's tools
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
