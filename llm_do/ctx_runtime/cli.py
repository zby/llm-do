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
    2. Else use "main" (must exist)

Toolsets:
    - Worker files reference toolsets by name in the toolsets: section
    - Python files export AbstractToolset instances (including FunctionToolset)
    - Built-in toolsets: shell, filesystem
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable, Coroutine, Union

from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.builtin_tools import (
    CodeExecutionTool,
    ImageGenerationTool,
    WebFetchTool,
    WebSearchTool,
)
from pydantic_ai_blocking_approval import (
    ApprovalToolset,
    ApprovalMemory,
    ApprovalRequest,
    ApprovalDecision,
)

from .ctx import Context, ApprovalFn, EventCallback
from .input_utils import coerce_worker_input
from .entries import WorkerEntry, ToolEntry
from .worker_file import load_worker_file
from .discovery import (
    load_toolsets_from_files,
    load_entries_from_files,
)
from .builtins import BUILTIN_TOOLSETS, get_builtin_toolset
from ..config_overrides import apply_overrides
from ..ui.events import UIEvent, ErrorEvent
from ..ui.display import (
    DisplayBackend,
    HeadlessDisplayBackend,
    JsonDisplayBackend,
    RichDisplayBackend,
)
from ..ui.parser import parse_approval_request


ENV_MODEL_VAR = "LLM_DO_MODEL"


# Registry of server-side tool factories
_BUILTIN_TOOL_FACTORIES: dict[str, Callable[[dict[str, Any]], Any]] = {
    "web_search": lambda cfg: WebSearchTool(
        max_uses=cfg.get("max_uses"),
        blocked_domains=cfg.get("blocked_domains"),
        allowed_domains=cfg.get("allowed_domains"),
    ),
    "web_fetch": lambda cfg: WebFetchTool(),
    "code_execution": lambda cfg: CodeExecutionTool(),
    "image_generation": lambda cfg: ImageGenerationTool(),
}


def _build_builtin_tools(configs: list[dict[str, Any]]) -> list[Any]:
    """Convert server_side_tools config to PydanticAI builtin_tools.

    Args:
        configs: List of tool config dicts from worker file (raw YAML)

    Returns:
        List of PydanticAI builtin tool instances
    """
    tools: list[Any] = []
    for config in configs:
        tool_type = config.get("tool_type")
        if not tool_type:
            raise ValueError("server_side_tools entry must have 'tool_type'")
        factory = _BUILTIN_TOOL_FACTORIES.get(tool_type)
        if not factory:
            raise ValueError(
                f"Unknown tool_type: {tool_type}. "
                f"Supported: {', '.join(_BUILTIN_TOOL_FACTORIES.keys())}"
            )
        tools.append(factory(config))
    return tools


# Type for approval callbacks (supports both sync and async)
ApprovalCallback = Callable[
    [ApprovalRequest],
    Union[ApprovalDecision, Awaitable[ApprovalDecision]]
]


def _wrap_toolsets_with_approval(
    toolsets: list[AbstractToolset[Any]],
    approve_all: bool,
    memory: ApprovalMemory,
    approval_callback: ApprovalCallback | None = None,
) -> list[AbstractToolset[Any]]:
    """Wrap toolsets with ApprovalToolset for approval handling.

    ApprovalToolset auto-detects if the inner toolset has needs_approval().
    Toolsets without needs_approval() are passed through unchanged.

    Args:
        toolsets: List of toolsets to wrap
        approve_all: If True, auto-approve all tool calls
        memory: Shared approval memory for tracking decisions
        approval_callback: Optional callback for interactive approval (TUI mode)

    Returns:
        List of wrapped toolsets
    """
    if approval_callback is None:
        def approval_callback(request: ApprovalRequest) -> ApprovalDecision:
            """Default approval callback for headless mode."""
            if approve_all:
                return ApprovalDecision(approved=True)
            # In headless mode without --approve-all, deny tools that need approval
            raise PermissionError(
                f"Tool '{request.tool_name}' requires approval. "
                f"Use --approve-all to auto-approve all tools in headless mode."
            )

    wrapped: list[AbstractToolset[Any]] = []
    for toolset in toolsets:
        # Recursively wrap toolsets inside WorkerEntry
        if isinstance(toolset, WorkerEntry) and toolset.toolsets:
            toolset = WorkerEntry(
                name=toolset.name,
                instructions=toolset.instructions,
                model=toolset.model,
                toolsets=_wrap_toolsets_with_approval(
                    toolset.toolsets, approve_all, memory, approval_callback
                ),
                builtin_tools=toolset.builtin_tools,
                schema_in=toolset.schema_in,
                schema_out=toolset.schema_out,
                requires_approval=toolset.requires_approval,
            )

        # Get any stored approval config from the toolset
        config = getattr(toolset, "_approval_config", None)

        # Wrap all toolsets with ApprovalToolset (secure by default)
        # - Toolsets with needs_approval() method: ApprovalToolset delegates to it
        # - Toolsets with _approval_config: uses config for per-tool pre-approval
        # - Other toolsets: all tools require approval unless --approve-all
        wrapped.append(ApprovalToolset(
            inner=toolset,
            approval_callback=approval_callback,
            memory=memory,
            config=config,
        ))

    return wrapped


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
    set_overrides: list[str] | None = None,
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
        set_overrides: Optional list of --set KEY=VALUE overrides

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
        # Apply overrides only to entry worker
        overrides = set_overrides if name == entry_name else None
        worker_file = load_worker_file(worker_path, overrides=overrides)

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
                toolset = all_toolsets[toolset_name]
                # Extract approval config for non-builtin toolsets (workers, Python toolsets)
                if isinstance(toolset_config, dict) and "_approval_config" in toolset_config:
                    toolset._approval_config = toolset_config["_approval_config"]  # type: ignore[attr-defined]
                resolved_toolsets.append(toolset)
            elif toolset_name in BUILTIN_TOOLSETS:
                toolset, approval_config = get_builtin_toolset(toolset_name, toolset_config)
                # Store approval config on the toolset for later use by ApprovalToolset
                if approval_config:
                    toolset._approval_config = approval_config  # type: ignore[attr-defined]
                resolved_toolsets.append(toolset)
            else:
                available_names = list(all_toolsets.keys()) + list(BUILTIN_TOOLSETS.keys())
                raise ValueError(f"Unknown toolset '{toolset_name}'. Available: {available_names}")

        # Apply model override only to entry worker (if override provided)
        if model and name == entry_name:
            worker_model = model
        else:
            worker_model = worker_file.model

        # Build builtin tools from server_side_tools config
        builtin_tools = _build_builtin_tools(worker_file.server_side_tools)

        stub = worker_entries[name]
        stub.instructions = worker_file.instructions
        stub.model = worker_model
        stub.toolsets = resolved_toolsets
        stub.builtin_tools = builtin_tools

        workers[name] = stub

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
    on_event: EventCallback | None = None,
    verbosity: int = 0,
    approval_callback: ApprovalCallback | None = None,
    set_overrides: list[str] | None = None,
) -> tuple[str, Context]:
    """Load entries and run with the given prompt.

    Args:
        files: List of .py and .worker files
        prompt: User prompt
        model: Optional model override
        entry_name: Optional entry point name (default: "main")
        all_tools: If True, make all entries available to the entry worker
        approve_all: If True, auto-approve all tool calls
        on_event: Optional callback for UI events (tool calls, streaming text)
        verbosity: Verbosity level (0=quiet, 1=progress, 2=streaming)
        approval_callback: Optional callback for interactive approval (TUI mode)
        set_overrides: Optional list of --set KEY=VALUE overrides

    Returns:
        Tuple of (result, context)
    """
    # Separate worker files and Python files
    worker_files = [f for f in files if f.endswith(".worker")]
    python_files = [f for f in files if f.endswith(".py")]

    # Build entry point
    resolved_entry_name = entry_name or "main"
    entry = await build_entry(worker_files, python_files, model, resolved_entry_name, set_overrides)

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
            builtin_tools=entry.builtin_tools,
            schema_in=entry.schema_in,
            schema_out=entry.schema_out,
        )

    # Wrap toolsets with ApprovalToolset for tool-level approval
    # This handles needs_approval() on toolsets like FileSystemToolset, ShellToolset
    memory = ApprovalMemory()
    if hasattr(entry, "toolsets") and entry.toolsets:
        wrapped_toolsets = _wrap_toolsets_with_approval(
            entry.toolsets, approve_all, memory, approval_callback
        )
        if isinstance(entry, WorkerEntry):
            entry = WorkerEntry(
                name=entry.name,
                instructions=entry.instructions,
                model=entry.model,
                toolsets=wrapped_toolsets,
                builtin_tools=entry.builtin_tools,
                schema_in=entry.schema_in,
                schema_out=entry.schema_out,
                requires_approval=entry.requires_approval,
            )
        elif isinstance(entry, ToolEntry):
            entry = ToolEntry(
                toolset=entry.toolset,
                tool_name=entry.tool_name,
                toolsets=wrapped_toolsets,
                model=entry.model,
                requires_approval=entry.requires_approval,
            )

    # Set up entry-level approval function (for entry.requires_approval)
    approval: ApprovalFn | None = None
    if approve_all:
        approval = lambda entry, input_data: True
    else:
        # In headless mode without --approve-all, deny entries that require approval
        def headless_approval(e: Any, data: Any) -> bool:
            if getattr(e, "requires_approval", False):
                raise PermissionError(
                    f"Entry '{e.name}' requires approval. "
                    f"Use --approve-all to auto-approve in headless mode."
                )
            return True
        approval = headless_approval

    # Create context from entry (entry.toolsets is already populated)
    ctx = Context.from_entry(
        entry,
        model=model,
        approval=approval,
        on_event=on_event,
        verbosity=verbosity,
    )

    if isinstance(entry, WorkerEntry):
        input_data = coerce_worker_input(entry.schema_in, prompt)
    else:
        input_data = {"input": prompt}

    result = await ctx.run(entry, input_data)

    return result, ctx


async def _run_tui_mode(
    files: list[str],
    prompt: str,
    model: str | None = None,
    entry_name: str | None = None,
    all_tools: bool = False,
    approve_all: bool = False,
    verbosity: int = 0,
    debug: bool = False,
    set_overrides: list[str] | None = None,
) -> int:
    """Run in Textual TUI mode with interactive approvals.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    from ..ui.app import LlmDoApp

    # Set up queues for app communication
    event_queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    approval_queue: asyncio.Queue[ApprovalDecision] = asyncio.Queue()

    # Create output buffer to capture events for post-TUI display
    output_buffer = io.StringIO()
    log_backend = RichDisplayBackend(output_buffer, force_terminal=True, verbosity=verbosity)

    # Container for result and exit code
    worker_result: list[Any] = []
    worker_exit_code: list[int] = [0]

    def emit_error_event(message: str, error_type: str) -> None:
        """Emit error event to TUI and log backend."""
        error_event = ErrorEvent(
            worker="worker",
            message=message,
            error_type=error_type,
        )
        event_queue.put_nowait(error_event)
        log_backend.display(error_event)
        worker_exit_code[0] = 1

    def on_event(event: UIEvent) -> None:
        """Forward events to both TUI and log buffer."""
        event_queue.put_nowait(event)
        log_backend.display(event)

    async def tui_approval_callback(request: ApprovalRequest) -> ApprovalDecision:
        """Async approval callback that sends to TUI and waits for response.

        This is called from ApprovalToolset.call_tool which is async, so we
        can await the queue response directly.
        """
        if approve_all:
            return ApprovalDecision(approved=True)

        # Parse the approval request into a typed event and send to TUI
        approval_event = parse_approval_request(request)
        event_queue.put_nowait(approval_event)

        # Await response from TUI
        return await approval_queue.get()

    async def run_worker_in_background() -> int:
        """Run the worker and send events to the app."""
        from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UserError

        try:
            result, ctx = await run(
                files=files,
                prompt=prompt,
                model=model,
                entry_name=entry_name,
                all_tools=all_tools,
                approve_all=approve_all,
                on_event=on_event,
                verbosity=verbosity,
                approval_callback=tui_approval_callback,
                set_overrides=set_overrides,
            )
            worker_result[:] = [result]
            return 0

        except FileNotFoundError as e:
            emit_error_event(f"Error: {e}", type(e).__name__)
            if debug:
                raise
            return 1
        except ValueError as e:
            emit_error_event(f"Error: {e}", type(e).__name__)
            if debug:
                raise
            return 1
        except PermissionError as e:
            emit_error_event(f"Error: {e}", type(e).__name__)
            if debug:
                raise
            return 1
        except ModelHTTPError as e:
            message = f"Model API error (status {e.status_code}): {e.model_name}"
            if e.body and isinstance(e.body, dict):
                error_info = e.body.get("error", {})
                if isinstance(error_info, dict):
                    msg = error_info.get("message", "")
                    if msg:
                        message = f"{message}\n  {msg}"
            emit_error_event(message, type(e).__name__)
            if debug:
                raise
            return 1
        except (UnexpectedModelBehavior, UserError) as e:
            emit_error_event(f"Error: {e}", type(e).__name__)
            if debug:
                raise
            return 1
        except KeyboardInterrupt:
            emit_error_event("Aborted by user", "KeyboardInterrupt")
            return 1
        except Exception as e:
            emit_error_event(f"Unexpected error: {e}", type(e).__name__)
            if debug:
                raise
            return 1
        finally:
            # Signal TUI that worker is done
            event_queue.put_nowait(None)

    # Create the Textual app with worker coroutine
    app = LlmDoApp(
        event_queue,
        approval_queue,
        worker_coro=run_worker_in_background(),
        auto_quit=True,
    )

    # Run with mouse disabled to allow terminal text selection
    await app.run_async(mouse=False)

    # Print captured output to stderr (session log)
    captured_output = output_buffer.getvalue()
    if captured_output:
        print(captured_output, file=sys.stderr)

    # Print final result to stdout
    if worker_result and verbosity < 2:
        result = worker_result[0]
        print(result)

    return worker_exit_code[0]


def main() -> int:
    """Main entry point for llm-run CLI.

    Returns:
        Exit code (0 for success, 1 for error)
    """
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
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Force headless mode (no TUI, plain text output)",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Force TUI mode (interactive UI)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show full tracebacks on error",
    )
    parser.add_argument(
        "--set", "-s",
        action="append",
        dest="set_overrides",
        default=[],
        metavar="KEY=VALUE",
        help="Override worker config (e.g., --set model=gpt-4, --set toolsets.shell.timeout=30)",
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

    # Validate mutually exclusive flags
    if args.json and args.tui:
        print("Cannot combine --json and --tui", file=sys.stderr)
        return 1
    if args.headless and args.tui:
        print("Cannot combine --headless and --tui", file=sys.stderr)
        return 1

    # Determine if we should use TUI mode:
    # - Explicit --tui flag
    # - Or: TTY available and not --headless and not --json
    use_tui = args.tui or (sys.stdout.isatty() and not args.headless and not args.json)

    # TUI mode
    if use_tui:
        return asyncio.run(_run_tui_mode(
            files=files,
            prompt=prompt,
            model=args.model,
            entry_name=args.entry,
            all_tools=args.all_tools,
            approve_all=args.approve_all,
            verbosity=args.verbose,
            debug=args.debug,
            set_overrides=args.set_overrides or None,
        ))

    # Headless mode: set up display backend based on flags
    backend: DisplayBackend | None = None
    on_event: EventCallback | None = None

    if args.json:
        backend = JsonDisplayBackend(stream=sys.stderr)
    elif args.verbose > 0:
        backend = HeadlessDisplayBackend(stream=sys.stderr, verbosity=args.verbose)

    if backend:
        def on_event_callback(event: UIEvent) -> None:
            backend.display(event)  # type: ignore[union-attr]
        on_event = on_event_callback

    # Import error types for handling
    from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UserError

    try:
        result, ctx = asyncio.run(run(
            files, prompt, args.model, args.entry, args.all_tools, args.approve_all,
            on_event, args.verbose, set_overrides=args.set_overrides or None
        ))

        # Don't print result when streaming (verbosity >= 2) since it was already streamed
        if args.verbose < 2:
            print(result)
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1
    except PermissionError as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1
    except ModelHTTPError as e:
        message = f"Model API error (status {e.status_code}): {e.model_name}"
        if e.body and isinstance(e.body, dict):
            error_info = e.body.get("error", {})
            if isinstance(error_info, dict):
                msg = error_info.get("message", "")
                if msg:
                    message = f"{message}\n  {msg}"
        print(message, file=sys.stderr)
        if args.debug:
            raise
        return 1
    except (UnexpectedModelBehavior, UserError) as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1
    except KeyboardInterrupt:
        print("\nAborted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main())
