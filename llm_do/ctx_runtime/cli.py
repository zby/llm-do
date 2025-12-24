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
from typing import Any, Callable

from pydantic_ai.toolsets import AbstractToolset

from .ctx import Context, ApprovalFn, CallTrace, TraceCallback
from .entries import WorkerEntry, ToolEntry
from .worker_file import load_worker_file
from .discovery import (
    load_toolsets_from_files,
    load_entries_from_files,
)
from .builtins import BUILTIN_TOOLSETS, get_builtin_toolset
from ..ui.events import ToolCallEvent, ToolResultEvent, StatusEvent, ErrorEvent, UIEvent
from ..ui.display import DisplayBackend, HeadlessDisplayBackend, JsonDisplayBackend


ENV_MODEL_VAR = "LLM_DO_MODEL"


def trace_to_event(trace: CallTrace) -> UIEvent:
    """Convert a CallTrace to the appropriate UIEvent."""
    if trace.kind == "tool":
        if trace.error:
            return ToolResultEvent(
                worker="",
                tool_name=trace.name,
                content=trace.error,
                is_error=True,
            )
        elif trace.output_data is not None:
            return ToolResultEvent(
                worker="",
                tool_name=trace.name,
                content=trace.output_data,
            )
        else:
            return ToolCallEvent(
                worker="",
                tool_name=trace.name,
                args=trace.input_data if isinstance(trace.input_data, dict) else {},
            )
    else:  # worker/entry
        if trace.error:
            return ErrorEvent(
                worker=trace.name,
                message=trace.error,
                error_type="ExecutionError",
            )
        elif trace.output_data is not None:
            return StatusEvent(
                worker=trace.name,
                phase="execution",
                state="completed",
            )
        else:
            return StatusEvent(
                worker=trace.name,
                phase="execution",
                state="started",
            )


async def _get_tool_names(toolset: AbstractToolset[Any]) -> list[str]:
    """Get tool names from a toolset without needing a RunContext."""
    from pydantic_ai.toolsets import FunctionToolset
    if isinstance(toolset, FunctionToolset):
        return list(toolset.tools.keys())
    # For other toolsets, we'd need a RunContext - return empty for now
    # WorkerEntry returns itself as a single tool
    if isinstance(toolset, WorkerEntry):
        return [toolset.name]
    return []


async def build_entry(
    worker_files: list[str],
    python_files: list[str],
    model: str | None = None,
    entry_name: str = "main",
) -> ToolEntry | WorkerEntry:
    """Build the entry point with all toolsets resolved.

    This function:
    1. Loads all Python toolsets and entries
    2. Creates WorkerEntry stubs for all .worker files (WorkerEntry IS an AbstractToolset)
    3. Resolves toolset references (workers can call other workers)
    4. Returns the entry (tool or worker) by name with toolsets populated

    Args:
        worker_files: List of .worker file paths
        python_files: List of Python file paths containing toolsets
        model: Optional model override for the entry worker
        entry_name: Name of the entry (default: "main")

    Returns:
        The ToolEntry or WorkerEntry to run, with toolsets attribute populated

    Raises:
        ValueError: If entry not found, name conflict, or unknown toolset
    """
    # Load Python toolsets
    python_toolsets = load_toolsets_from_files(python_files)

    # Build map of tool_name -> toolset for code entry pattern
    python_tool_map: dict[str, tuple[AbstractToolset[Any], str]] = {}
    for toolset_name, toolset in python_toolsets.items():
        tool_names = await _get_tool_names(toolset)
        for tool_name in tool_names:
            python_tool_map[tool_name] = (toolset, tool_name)

    # Load Python WorkerEntry instances
    python_workers = load_entries_from_files(python_files)

    if not worker_files and not python_tool_map and not python_workers:
        raise ValueError("At least one .worker or .py file with entries required")

    # First pass: create stub WorkerEntry instances (they ARE AbstractToolsets)
    worker_entries: dict[str, WorkerEntry] = {}
    worker_paths: dict[str, str] = {}  # name -> path

    for worker_path in worker_files:
        worker_file = load_worker_file(worker_path)
        name = worker_file.name

        # Check for duplicate worker names
        if name in worker_entries:
            raise ValueError(f"Duplicate worker name: {name}")

        # Check for conflict with Python entries
        if name in python_workers or name in python_tool_map:
            raise ValueError(f"Worker name '{name}' conflicts with Python entry")

        stub = WorkerEntry(
            name=name,
            instructions=worker_file.instructions,
            model=worker_file.model,
            toolsets=[],
        )
        worker_entries[name] = stub
        worker_paths[name] = worker_path

    # Determine entry type: worker file, Python worker, or Python tool
    entry_type: str
    if entry_name in worker_entries:
        entry_type = "worker_file"
    elif entry_name in python_workers:
        entry_type = "python_worker"
    elif entry_name in python_tool_map:
        entry_type = "python_tool"
    else:
        available = list(worker_entries.keys()) + list(python_workers.keys()) + list(python_tool_map.keys())
        raise ValueError(f"Entry '{entry_name}' not found. Available: {available}")

    # Second pass: build all workers with resolved toolsets
    workers: dict[str, WorkerEntry] = {}

    for name, worker_path in worker_paths.items():
        worker_file = load_worker_file(worker_path)

        # Available toolsets: Python + other workers (not self)
        # WorkerEntry IS an AbstractToolset, so we can use it directly
        available_workers = {k: v for k, v in worker_entries.items() if k != name}
        all_toolsets: dict[str, AbstractToolset[Any]] = {}
        all_toolsets.update(python_toolsets)
        all_toolsets.update(available_workers)

        # Resolve toolsets by name
        resolved_toolsets: list[AbstractToolset[Any]] = []

        for toolset_name, toolset_config in worker_file.toolsets.items():
            if toolset_name in all_toolsets:
                resolved_toolsets.append(all_toolsets[toolset_name])
            elif toolset_name in BUILTIN_TOOLSETS:
                toolset = get_builtin_toolset(toolset_name, toolset_config)
                resolved_toolsets.append(toolset)
            else:
                available_names = list(all_toolsets.keys()) + list(BUILTIN_TOOLSETS.keys())
                raise ValueError(f"Unknown toolset '{toolset_name}'. Available: {available_names}")

        # Apply model override only to entry worker
        worker_model = model if name == entry_name else worker_file.model

        workers[name] = WorkerEntry(
            name=name,
            instructions=worker_file.instructions,
            model=worker_model,
            toolsets=resolved_toolsets,
        )

        # Update worker_entries with fully built worker
        worker_entries[name] = workers[name]

    # Return entry
    if entry_type == "worker_file":
        return workers[entry_name]
    elif entry_type == "python_worker":
        return python_workers[entry_name]
    else:  # python_tool
        # Build list of all available toolsets for code entry points
        all_toolsets_list: list[AbstractToolset[Any]] = []
        all_toolsets_list.extend(worker_entries.values())
        all_toolsets_list.extend(python_toolsets.values())

        # Create ToolEntry for the code entry point
        toolset, tool_name = python_tool_map[entry_name]
        return ToolEntry(
            toolset=toolset,
            tool_name=tool_name,
            toolsets=all_toolsets_list,
        )


async def run(
    files: list[str],
    prompt: str,
    model: str | None = None,
    entry_name: str | None = None,
    all_tools: bool = False,
    approve_all: bool = False,
    on_trace: TraceCallback | None = None,
) -> tuple[str, Context]:
    """Load entries and run with the given prompt.

    Args:
        files: List of .py and .worker files
        prompt: User prompt
        model: Optional model override
        entry_name: Optional entry point name (default: "main")
        all_tools: If True, make all entries available to the entry worker
        approve_all: If True, auto-approve all tool calls
        on_trace: Optional callback for trace events (real-time progress)

    Returns:
        Tuple of (result, context)
    """
    # Separate worker files and Python files
    worker_files = [f for f in files if f.endswith(".worker")]
    python_files = [f for f in files if f.endswith(".py")]

    # Build entry point
    resolved_entry_name = entry_name or "main"
    entry = await build_entry(worker_files, python_files, model, resolved_entry_name)

    # If --all-tools and entry is a worker, give it access to all discovered toolsets
    if all_tools and isinstance(entry, WorkerEntry):
        discovered_toolsets = load_toolsets_from_files(python_files)
        # Add any toolsets not already in the entry's toolsets
        existing_ids = {getattr(ts, 'id', None) or id(ts) for ts in entry.toolsets}
        additional = [ts for ts in discovered_toolsets.values()
                      if (getattr(ts, 'id', None) or id(ts)) not in existing_ids]

        entry = WorkerEntry(
            name=entry.name,
            instructions=entry.instructions,
            model=entry.model or model,
            toolsets=list(entry.toolsets) + additional,
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

    # Create context from entry (entry.toolsets is already populated)
    ctx = Context.from_entry(
        entry,
        model=model,
        approval=approval,
        on_trace=on_trace,
    )

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
    parser.add_argument("--trace", action="store_true", help="Show execution trace after completion")
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Show progress (-v for tool calls, -vv for streaming)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output events as JSON lines (for piping/automation)",
    )

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

    # Set up display backend based on flags
    backend: DisplayBackend | None = None
    on_trace: TraceCallback | None = None

    if args.json:
        backend = JsonDisplayBackend(stream=sys.stderr)
    elif args.verbose > 0:
        backend = HeadlessDisplayBackend(stream=sys.stderr, verbosity=args.verbose)

    if backend:
        def on_trace_callback(trace: CallTrace) -> None:
            event = trace_to_event(trace)
            backend.display(event)  # type: ignore[union-attr]
        on_trace = on_trace_callback

    result, ctx = asyncio.run(run(
        files, prompt, args.model, args.entry, args.all_tools, args.approve_all, on_trace
    ))
    print(result)

    if args.trace:
        print("\n--- Trace ---", file=sys.stderr)
        for t in ctx.trace:
            print(f"  {t.name} ({t.kind}) depth={t.depth}", file=sys.stderr)


if __name__ == "__main__":
    main()
