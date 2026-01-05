#!/usr/bin/env python
"""Run an LLM worker with tools loaded from Python and/or worker files.

Usage:
    llm-do <worker.worker> [tools.py...] "Your prompt here"
    llm-do <worker.worker> [tools.py...] --entry NAME "Your prompt"

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
import os
import sys
from pathlib import Path
from typing import Any, Callable, Literal, cast

from pydantic_ai.builtin_tools import (
    CodeExecutionTool,
    ImageGenerationTool,
    WebFetchTool,
    WebSearchTool,
)
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalRequest

from ..runtime import (
    ApprovalCallback,
    EventCallback,
    Invocable,
    RunApprovalPolicy,
    ToolInvocable,
    Worker,
    WorkerRuntime,
    load_worker_file,
    run_invocable,
)
from ..runtime.discovery import load_toolsets_and_workers_from_files
from ..toolsets.loader import (
    ToolsetBuildContext,
    build_toolsets,
    extract_toolset_approval_configs,
)
from ..ui import (
    DisplayBackend,
    ErrorEvent,
    HeadlessDisplayBackend,
    JsonDisplayBackend,
    RichDisplayBackend,
    TextualDisplayBackend,
    UIEvent,
    parse_approval_request,
)

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


async def _get_tool_names(toolset: AbstractToolset[Any]) -> list[str]:
    """Get tool names from a toolset without needing a RunContext."""
    from pydantic_ai.toolsets import FunctionToolset
    if isinstance(toolset, FunctionToolset):
        return list(toolset.tools.keys())
    # For other toolsets, we'd need a RunContext - return empty for now
    # Worker returns itself as a single tool
    if isinstance(toolset, Worker):
        return [toolset.name]
    return []


async def build_entry(
    worker_files: list[str],
    python_files: list[str],
    model: str | None = None,
    entry_name: str = "main",
    set_overrides: list[str] | None = None,
) -> ToolInvocable | Worker:
    """Build the entry point with all toolsets resolved.

    This function:
    1. Loads all Python toolsets and workers
    2. Creates Worker stubs for all .worker files (Worker IS an AbstractToolset)
    3. Resolves toolset references (workers can call other workers)
    4. Returns the entry (tool or worker) by name with toolsets populated

    Args:
        worker_files: List of .worker file paths
        python_files: List of Python file paths containing toolsets
        model: Optional model override for the entry worker
        entry_name: Name of the entry (default: "main")
        set_overrides: Optional list of --set KEY=VALUE overrides

    Returns:
        The ToolInvocable or Worker to run, with toolsets attribute populated

    Raises:
        ValueError: If entry not found, name conflict, or unknown toolset
    """
    # Load Python toolsets and workers in a single pass
    python_toolsets, python_workers = load_toolsets_and_workers_from_files(python_files)

    # Build map of tool_name -> toolset for code entry pattern
    python_tool_map: dict[str, tuple[AbstractToolset[Any], str, str]] = {}
    for toolset_name, toolset in python_toolsets.items():
        tool_names = await _get_tool_names(toolset)
        for tool_name in tool_names:
            if tool_name in python_tool_map:
                _, _, existing_toolset_name = python_tool_map[tool_name]
                raise ValueError(
                    f"Duplicate tool name: {tool_name} "
                    f"(from toolsets '{existing_toolset_name}' and '{toolset_name}')"
                )
            python_tool_map[tool_name] = (toolset, tool_name, toolset_name)

    if not worker_files and not python_tool_map and not python_workers:
        raise ValueError("At least one .worker or .py file with entries required")

    # First pass: create stub Worker instances (they ARE AbstractToolsets)
    worker_entries: dict[str, Worker] = {}
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

        stub = Worker(
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
    workers: dict[str, Worker] = {}

    for name, worker_path in worker_paths.items():
        # Apply overrides only to entry worker
        overrides = set_overrides if name == entry_name else None
        worker_file = load_worker_file(worker_path, overrides=overrides)

        # Available toolsets: Python + other workers (not self)
        # Worker IS an AbstractToolset, so we can use it directly
        available_workers = {k: v for k, v in worker_entries.items() if k != name}
        all_toolsets: dict[str, AbstractToolset[Any]] = {}
        all_toolsets.update(python_toolsets)
        all_toolsets.update(available_workers)

        # Resolve toolsets: worker refs + python toolsets + (built-in aliases or class paths)
        toolset_context = ToolsetBuildContext(
            worker_name=name,
            worker_path=Path(worker_path).resolve(),
            available_toolsets=all_toolsets,
        )
        resolved_toolsets = build_toolsets(worker_file.toolsets, toolset_context)
        approval_configs = extract_toolset_approval_configs(worker_file.toolsets)

        # Apply model override only to entry worker (if override provided)
        worker_model: str | None
        if model and name == entry_name:
            worker_model = model
        else:
            worker_model = worker_file.model

        # Build builtin tools from server_side_tools config
        builtin_tools = _build_builtin_tools(worker_file.server_side_tools)

        stub = worker_entries[name]
        stub.instructions = worker_file.instructions
        stub.model = worker_model
        stub.compatible_models = worker_file.compatible_models
        stub.toolsets = resolved_toolsets
        stub.toolset_approval_configs = approval_configs
        stub.builtin_tools = builtin_tools

        workers[name] = stub

    # Return entry
    if entry_type == "worker_file":
        return workers[entry_name]
    elif entry_type == "python_worker":
        return python_workers[entry_name]
    else:  # python_tool
        # Create ToolInvocable for the code entry point
        toolset, tool_name, _toolset_name = python_tool_map[entry_name]
        return ToolInvocable(
            toolset=toolset,
            tool_name=tool_name,
        )


async def run(
    files: list[str],
    prompt: str,
    model: str | None = None,
    entry_name: str | None = None,
    approve_all: bool = False,
    reject_all: bool = False,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
    approval_callback: ApprovalCallback | None = None,
    approval_cache: dict[Any, ApprovalDecision] | None = None,
    return_permission_errors: bool = False,
    message_history: list[Any] | None = None,
    set_overrides: list[str] | None = None,
) -> tuple[Any, WorkerRuntime]:
    """Load entries and run with the given prompt.

    Args:
        files: List of .py and .worker files
        prompt: User prompt
        model: Optional model override
        entry_name: Optional entry point name (default: "main")
        approve_all: If True, auto-approve all tool calls
        reject_all: If True, auto-reject all tool calls that require approval
        on_event: Optional callback for UI events (tool calls, streaming text)
        verbosity: Verbosity level (0=quiet, 1=progress, 2=streaming)
        approval_callback: Optional interactive approval callback (TUI mode)
        approval_cache: Optional shared cache for remember="session" approvals
        return_permission_errors: If True, return tool results on PermissionError
        message_history: Optional prior messages for multi-turn conversations
        set_overrides: Optional list of --set KEY=VALUE overrides

    Returns:
        Tuple of (result, context)
    """
    if approve_all and reject_all:
        raise ValueError("Cannot set both approve_all and reject_all")

    # Separate worker files and Python files
    worker_files = [f for f in files if f.endswith(".worker")]
    python_files = [f for f in files if f.endswith(".py")]

    # Build entry point
    resolved_entry_name = entry_name or "main"
    entry = await build_entry(worker_files, python_files, model, resolved_entry_name, set_overrides)

    approval_mode: Literal["prompt", "approve_all", "reject_all"] = "prompt"
    if approve_all:
        approval_mode = "approve_all"
    elif reject_all:
        approval_mode = "reject_all"

    approval_policy = RunApprovalPolicy(
        mode=approval_mode,
        approval_callback=approval_callback,
        cache=approval_cache,
        return_permission_errors=return_permission_errors,
    )

    invocable = cast(Invocable, entry)
    return await run_invocable(
        invocable,
        prompt,
        model=model,
        approval_policy=approval_policy,
        on_event=on_event,
        verbosity=verbosity,
        message_history=message_history,
    )


async def _run_tui_mode(
    files: list[str],
    prompt: str,
    model: str | None = None,
    entry_name: str | None = None,
    approve_all: bool = False,
    reject_all: bool = False,
    verbosity: int = 0,
    chat: bool = False,
    debug: bool = False,
    set_overrides: list[str] | None = None,
) -> int:
    """Run in Textual TUI mode with interactive approvals.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    from ..ui.app import LlmDoApp

    app: LlmDoApp | None = None

    # Set up queues for render pipeline and app communication
    render_queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    tui_event_queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    approval_queue: asyncio.Queue[ApprovalDecision] = asyncio.Queue()
    # Shared across turns for remember="session" approvals.
    approval_cache: dict[Any, ApprovalDecision] = {}

    # Create output buffer to capture events for post-TUI display
    output_buffer = io.StringIO()
    log_backend = RichDisplayBackend(output_buffer, force_terminal=True, verbosity=verbosity)
    tui_backend = TextualDisplayBackend(tui_event_queue)

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
        render_queue.put_nowait(error_event)
        worker_exit_code[0] = 1

    def on_event(event: UIEvent) -> None:
        """Forward events to the render pipeline."""
        render_queue.put_nowait(event)

    async def render_loop() -> None:
        """Render UI events through the configured backends."""
        backends = (tui_backend, log_backend)
        for backend in backends:
            await backend.start()
        try:
            while True:
                event = await render_queue.get()
                if event is None:
                    tui_event_queue.put_nowait(None)
                    render_queue.task_done()
                    break
                for backend in backends:
                    backend.display(event)
                render_queue.task_done()
        finally:
            for backend in backends:
                await backend.stop()

    async def _prompt_approval_in_tui(request: ApprovalRequest) -> ApprovalDecision:
        """Send an approval request to the TUI and await the user's decision."""
        approval_event = parse_approval_request(request)
        render_queue.put_nowait(approval_event)
        return await approval_queue.get()

    async def run_turn(
        user_prompt: str,
        message_history: list[Any] | None,
    ) -> list[Any] | None:
        """Run a single conversation turn and return updated message history."""
        from pydantic_ai.exceptions import (
            ModelHTTPError,
            UnexpectedModelBehavior,
            UserError,
        )

        try:
            result, ctx = await run(
                files=files,
                prompt=user_prompt,
                model=model,
                entry_name=entry_name,
                approve_all=approve_all,
                reject_all=reject_all,
                on_event=on_event,
                verbosity=verbosity,
                approval_callback=_prompt_approval_in_tui,
                approval_cache=approval_cache,
                return_permission_errors=True,
                message_history=message_history,
                set_overrides=set_overrides,
            )
            worker_result[:] = [result]
            return list(ctx.messages)

        except FileNotFoundError as e:
            emit_error_event(f"Error: {e}", type(e).__name__)
            if debug:
                raise
        except ValueError as e:
            emit_error_event(f"Error: {e}", type(e).__name__)
            if debug:
                raise
        except PermissionError as e:
            emit_error_event(f"Error: {e}", type(e).__name__)
            if debug:
                raise
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
        except (UnexpectedModelBehavior, UserError) as e:
            emit_error_event(f"Error: {e}", type(e).__name__)
            if debug:
                raise
        except KeyboardInterrupt:
            emit_error_event("Aborted by user", "KeyboardInterrupt")
        except Exception as e:
            emit_error_event(f"Unexpected error: {e}", type(e).__name__)
            if debug:
                raise

        worker_exit_code[0] = 1
        return None

    async def run_worker_in_background() -> int:
        """Run the worker and send events to the app."""
        history = await run_turn(prompt, None)
        if history is not None and app is not None:
            app.set_message_history(history)
        if not chat:
            render_queue.put_nowait(None)
        return worker_exit_code[0]

    # Create the Textual app with worker coroutine
    app = LlmDoApp(
        tui_event_queue,
        approval_queue,
        worker_coro=run_worker_in_background(),
        run_turn=run_turn if chat else None,
        auto_quit=not chat,
    )

    # Run with mouse disabled to allow terminal text selection
    render_task = asyncio.create_task(render_loop())
    await app.run_async(mouse=False)
    render_queue.put_nowait(None)
    if not render_task.done():
        await render_task

    # Print captured output to stderr (session log)
    captured_output = output_buffer.getvalue()
    if captured_output:
        print(captured_output, file=sys.stderr)

    # Print final result to stdout
    if worker_result and verbosity < 2:
        result = worker_result[0]
        print(result)

    return worker_exit_code[0]


async def _run_headless_mode(
    files: list[str],
    prompt: str,
    model: str | None,
    entry_name: str | None,
    approve_all: bool,
    reject_all: bool,
    verbosity: int,
    backend: DisplayBackend | None,
    set_overrides: list[str] | None,
) -> str:
    """Run in headless/JSON mode with the display backend pipeline."""
    render_task: asyncio.Task[None] | None = None
    render_queue: asyncio.Queue[UIEvent | None] | None = None
    on_event: EventCallback | None = None

    if backend is not None:
        render_queue = asyncio.Queue()

        def on_event_callback(event: UIEvent) -> None:
            render_queue.put_nowait(event)

        on_event = on_event_callback

        async def render_loop() -> None:
            await backend.start()
            try:
                while True:
                    event = await render_queue.get()
                    if event is None:
                        render_queue.task_done()
                        break
                    backend.display(event)
                    render_queue.task_done()
            finally:
                await backend.stop()

        render_task = asyncio.create_task(render_loop())

    try:
        result, _ctx = await run(
            files=files,
            prompt=prompt,
            model=model,
            entry_name=entry_name,
            approve_all=approve_all,
            reject_all=reject_all,
            on_event=on_event,
            verbosity=verbosity,
            set_overrides=set_overrides,
        )
    finally:
        if render_queue is not None:
            render_queue.put_nowait(None)
            if render_task is not None and not render_task.done():
                await render_task

    return result


def main() -> int:
    """Main entry point for llm-do CLI.

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
    parser.add_argument(
        "--model", "-m",
        default=os.environ.get(ENV_MODEL_VAR),
        help=f"Model to use (default: ${ENV_MODEL_VAR} env var)",
    )
    parser.add_argument(
        "--approve-all",
        action="store_true",
        help="Auto-approve all LLM-invoked tool calls",
    )
    parser.add_argument(
        "--reject-all",
        action="store_true",
        help="Auto-reject all LLM-invoked tool calls that require approval",
    )
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
        "--chat",
        action="store_true",
        help="Enable multi-turn chat mode in the TUI",
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
        help=(
            "Override worker config (e.g., --set model=gpt-4, "
            "--set toolsets.shell.timeout=30, "
            "--set 'toolsets[\"llm_do.toolsets.shell.ShellToolset\"].default.approval_required=false')"
        ),
    )

    parse_args = getattr(parser, "parse_intermixed_args", parser.parse_args)
    args = parse_args()

    # Separate files from prompt in the files list (prompt might be mixed in)
    files = []
    prompt_parts = []
    missing_files = []
    for arg in args.files:
        if Path(arg).suffix in (".py", ".worker"):
            if Path(arg).exists():
                files.append(arg)
            else:
                missing_files.append(arg)
        else:
            prompt_parts.append(arg)

    if missing_files:
        parser.error(f"File not found: {', '.join(missing_files)}")

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
    if args.approve_all and args.reject_all:
        print("Cannot combine --approve-all and --reject-all", file=sys.stderr)
        return 1
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
    if args.chat and not use_tui:
        print("Chat mode requires TUI (--tui or a TTY).", file=sys.stderr)
        return 1

    if use_tui:
        tui_verbosity = args.verbose if args.verbose > 0 else 1
        return asyncio.run(_run_tui_mode(
            files=files,
            prompt=prompt,
            model=args.model,
            entry_name=args.entry,
            approve_all=args.approve_all,
            reject_all=args.reject_all,
            verbosity=tui_verbosity,
            chat=args.chat,
            debug=args.debug,
            set_overrides=args.set_overrides or None,
        ))

    # Headless mode: set up display backend based on flags
    backend: DisplayBackend | None = None

    if args.json:
        backend = JsonDisplayBackend(stream=sys.stderr)
    elif args.verbose > 0:
        backend = HeadlessDisplayBackend(stream=sys.stderr, verbosity=args.verbose)

    # Import error types for handling
    from pydantic_ai.exceptions import (
        ModelHTTPError,
        UnexpectedModelBehavior,
        UserError,
    )

    try:
        result = asyncio.run(_run_headless_mode(
            files=files,
            prompt=prompt,
            model=args.model,
            entry_name=args.entry,
            approve_all=args.approve_all,
            reject_all=args.reject_all,
            verbosity=args.verbose,
            backend=backend,
            set_overrides=args.set_overrides or None,
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
