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
    - Built-in toolsets: shell_readonly, shell_file_ops, filesystem_cwd, filesystem_project
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalRequest

from ..runtime import (
    ApprovalCallback,
    EventCallback,
    RunApprovalPolicy,
    Runtime,
    WorkerRuntime,
)
from ..runtime.registry import EntryRegistry, build_entry_registry
from ..ui import (
    DisplayBackend,
    ErrorEvent,
    HeadlessDisplayBackend,
    JsonDisplayBackend,
    TextualDisplayBackend,
    UIEvent,
    parse_approval_request,
)

ENV_MODEL_VAR = "LLM_DO_MODEL"


def _ensure_stdout_textual_driver() -> None:
    """Configure Textual to write TUI output to stdout on Linux."""
    if sys.platform.startswith("win"):
        return
    if os.environ.get("TEXTUAL_DRIVER"):
        return
    if "StdoutLinuxDriver" in globals():
        return

    os.environ["TEXTUAL_DRIVER"] = "llm_do.cli.main:StdoutLinuxDriver"

    from textual.drivers.linux_driver import LinuxDriver

    class StdoutLinuxDriver(LinuxDriver):
        def __init__(
            self,
            app: Any,
            *,
            debug: bool = False,
            mouse: bool = True,
            size: tuple[int, int] | None = None,
        ) -> None:
            super().__init__(app, debug=debug, mouse=mouse, size=size)
            self._file = sys.__stdout__

    globals()["StdoutLinuxDriver"] = StdoutLinuxDriver


def _make_message_log_callback(stream: Any) -> Callable[[str, int, list[Any]], None]:
    """Stream raw model request/response messages as JSONL."""
    counter = itertools.count()

    def callback(worker: str, depth: int, messages: list[Any]) -> None:
        try:
            serialized = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
        except Exception:
            serialized = []
            for msg in messages:
                try:
                    serialized.append(ModelMessagesTypeAdapter.dump_python([msg], mode="json")[0])
                except Exception:
                    serialized.append({"repr": repr(msg)})

        for message in serialized:
            record = {
                "seq": next(counter),
                "worker": worker,
                "depth": depth,
                "message": message,
            }
            stream.write(json.dumps(record, ensure_ascii=True, indent=2) + "\n")
        stream.flush()

    return callback


async def run(
    files: list[str],
    prompt: str,
    model: str | None = None,
    entry_name: str | None = None,
    max_depth: int | None = None,
    approve_all: bool = False,
    reject_all: bool = False,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
    approval_callback: ApprovalCallback | None = None,
    approval_cache: dict[Any, ApprovalDecision] | None = None,
    return_permission_errors: bool = False,
    message_history: list[Any] | None = None,
    set_overrides: list[str] | None = None,
    registry: EntryRegistry | None = None,
    runtime: Runtime | None = None,
) -> tuple[Any, WorkerRuntime]:
    """Load entries and run with the given prompt.

    Args:
        files: List of .py and .worker files
        prompt: User prompt text
        model: Optional model override
        entry_name: Optional entry point name (default: "main")
        max_depth: Optional maximum worker call depth
        approve_all: If True, auto-approve all tool calls
        reject_all: If True, auto-reject all tool calls that require approval
        on_event: Optional callback for UI events (tool calls, streaming text)
        verbosity: Verbosity level (0=quiet, 1=progress, 2=streaming)
        approval_callback: Optional interactive approval callback (TUI mode)
        approval_cache: Optional shared cache for remember="session" approvals
        return_permission_errors: If True, return tool results on PermissionError
        message_history: Optional prior messages for multi-turn conversations
        set_overrides: Optional list of --set KEY=VALUE overrides
        registry: Optional pre-built registry (skips registry build if provided)
        runtime: Optional pre-built runtime (skips approval/UI wiring if provided)

    Returns:
        Tuple of (result, context)
    """
    if approve_all and reject_all:
        raise ValueError("Cannot set both approve_all and reject_all")

    resolved_entry_name = entry_name or "main"

    if registry is None:
        # Separate worker files and Python files
        worker_files = [f for f in files if f.endswith(".worker")]
        python_files = [f for f in files if f.endswith(".py")]
        registry = build_entry_registry(
            worker_files,
            python_files,
            entry_name=resolved_entry_name,
            entry_model_override=model,
            set_overrides=set_overrides,
        )
    if runtime is None:
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
        message_log_callback = None
        if verbosity >= 3:
            message_log_callback = _make_message_log_callback(sys.stderr)
        runtime = Runtime(
            cli_model=model,
            run_approval_policy=approval_policy,
            max_depth=max_depth if max_depth is not None else 5,
            on_event=on_event,
            message_log_callback=message_log_callback,
            verbosity=verbosity,
        )
    else:
        if (
            approve_all
            or reject_all
            or approval_callback is not None
            or approval_cache is not None
            or return_permission_errors
            or max_depth is not None
            or on_event is not None
            or verbosity != 0
        ):
            raise ValueError("runtime provided; do not pass approval/UI overrides")

    return await runtime.run_entry(
        registry,
        resolved_entry_name,
        {"input": prompt},
        model=model,
        message_history=message_history,
    )


async def _run_tui_mode(
    files: list[str],
    prompt: str,
    model: str | None = None,
    entry_name: str | None = None,
    max_depth: int | None = None,
    approve_all: bool = False,
    reject_all: bool = False,
    verbosity: int = 0,
    log_verbosity: int = 0,
    chat: bool = False,
    debug: bool = False,
    set_overrides: list[str] | None = None,
) -> int:
    """Run in Textual TUI mode with interactive approvals.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    _ensure_stdout_textual_driver()
    from ..ui.app import LlmDoApp

    app: LlmDoApp | None = None

    # Set up queues for render pipeline and app communication
    render_queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    tui_event_queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    approval_queue: asyncio.Queue[ApprovalDecision] = asyncio.Queue()

    log_backend: HeadlessDisplayBackend | None = None
    if 0 < log_verbosity < 3:
        log_backend = HeadlessDisplayBackend(sys.stderr, verbosity=log_verbosity)
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
        backends: list[DisplayBackend] = [tui_backend]
        if log_backend is not None:
            backends.append(log_backend)
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

    approval_mode: Literal["prompt", "approve_all", "reject_all"] = "prompt"
    if approve_all:
        approval_mode = "approve_all"
    elif reject_all:
        approval_mode = "reject_all"

    approval_policy = RunApprovalPolicy(
        mode=approval_mode,
        approval_callback=_prompt_approval_in_tui,
        return_permission_errors=True,
    )
    message_log_callback = None
    if log_verbosity >= 3:
        message_log_callback = _make_message_log_callback(sys.stderr)
    runtime = Runtime(
        cli_model=model,
        run_approval_policy=approval_policy,
        max_depth=max_depth if max_depth is not None else 5,
        on_event=on_event,
        message_log_callback=message_log_callback,
        verbosity=verbosity,
    )

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
                message_history=message_history,
                set_overrides=set_overrides,
                runtime=runtime,
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

    # Print final result to stdout
    if worker_result:
        result = worker_result[0]
        print(result)

    return worker_exit_code[0]


async def _run_headless_mode(
    files: list[str],
    prompt: str,
    model: str | None,
    entry_name: str | None,
    max_depth: int | None,
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
            max_depth=max_depth,
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
        help=(
            "Show progress (-v for tool calls, -vv for streaming, "
            "-vvv for full LLM message log JSONL only)"
        ),
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Maximum worker call depth (default: 5)",
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
            "--set description='Fast run', "
            "--set 'server_side_tools=[{\"tool_type\":\"web_search\"}]')"
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
            max_depth=args.max_depth,
            approve_all=args.approve_all,
            reject_all=args.reject_all,
            verbosity=tui_verbosity,
            log_verbosity=args.verbose,
            chat=args.chat,
            debug=args.debug,
            set_overrides=args.set_overrides or None,
        ))

    # Headless mode: set up display backend based on flags
    backend: DisplayBackend | None = None

    if args.json:
        backend = JsonDisplayBackend(stream=sys.stderr)
    elif 0 < args.verbose < 3:
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
            max_depth=args.max_depth,
            approve_all=args.approve_all,
            reject_all=args.reject_all,
            verbosity=args.verbose,
            backend=backend,
            set_overrides=args.set_overrides or None,
        ))

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
