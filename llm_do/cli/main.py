#!/usr/bin/env python
"""Run an LLM worker using a manifest-driven project configuration.

Usage:
    llm-do project.json [prompt]
    llm-do project.json --input-json '{"input": "Your prompt"}'

The manifest file (JSON) specifies runtime config and file paths; the entry is
resolved from the file set (worker marked `entry: true` or a single `@entry` function).
CLI input (prompt or --input-json) overrides manifest entry.input when allowed.
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
    Entry,
    EventCallback,
    RunApprovalPolicy,
    Runtime,
    WorkerRuntime,
    build_entry,
)
from ..runtime.manifest import (
    ProjectManifest,
    load_manifest,
    resolve_manifest_paths,
)
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
    manifest: ProjectManifest,
    manifest_dir: Path,
    input_data: dict[str, Any],
    *,
    model_override: str | None = None,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
    approval_callback: ApprovalCallback | None = None,
    approval_cache: dict[Any, ApprovalDecision] | None = None,
    message_history: list[Any] | None = None,
    entry: Entry | None = None,
    runtime: Runtime | None = None,
) -> tuple[Any, WorkerRuntime]:
    """Load entries from manifest and run with the given input.

    Args:
        manifest: The validated project manifest
        manifest_dir: Directory containing the manifest file
        input_data: Input data for the entry point
        model_override: Optional model override (from env var)
        on_event: Optional callback for UI events (tool calls, streaming text)
        verbosity: Verbosity level (0=quiet, 1=progress, 2=streaming)
        approval_callback: Optional interactive approval callback (TUI mode)
        approval_cache: Optional shared cache for remember="session" approvals
        message_history: Optional prior messages for multi-turn conversations
        entry: Optional pre-built entry (skips entry build if provided)
        runtime: Optional pre-built runtime (skips approval/UI wiring if provided)

    Returns:
        Tuple of (result, context)
    """
    # Resolve file paths relative to manifest directory
    worker_paths, python_paths = resolve_manifest_paths(manifest, manifest_dir)

    # Determine effective model: entry.model > runtime.model > env var
    effective_model = (
        manifest.entry.model
        or manifest.runtime.model
        or model_override
    )

    if entry is None:
        entry = build_entry(
            [str(p) for p in worker_paths],
            [str(p) for p in python_paths],
            entry_model_override=effective_model,
        )

    if runtime is None:
        approval_mode: Literal["prompt", "approve_all", "reject_all"] = manifest.runtime.approval_mode

        approval_policy = RunApprovalPolicy(
            mode=approval_mode,
            approval_callback=approval_callback,
            cache=approval_cache,
            return_permission_errors=manifest.runtime.return_permission_errors,
        )
        message_log_callback = None
        if verbosity >= 3:
            message_log_callback = _make_message_log_callback(sys.stderr)
        runtime = Runtime(
            cli_model=effective_model,
            run_approval_policy=approval_policy,
            max_depth=manifest.runtime.max_depth,
            on_event=on_event,
            message_log_callback=message_log_callback,
            verbosity=verbosity,
        )
    else:
        if (
            approval_callback is not None
            or approval_cache is not None
            or on_event is not None
            or verbosity != 0
        ):
            raise ValueError("runtime provided; do not pass approval/UI overrides")

    return await runtime.run_entry(
        entry,
        input_data,
        model=effective_model,
        message_history=message_history,
    )


async def _run_tui_mode(
    manifest: ProjectManifest,
    manifest_dir: Path,
    input_data: dict[str, Any],
    *,
    model_override: str | None = None,
    verbosity: int = 0,
    log_verbosity: int = 0,
    chat: bool = False,
    debug: bool = False,
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
        if log_backend is None:
            print(
                f"[worker] ERROR ({error_type}): {message}",
                file=sys.__stderr__,
                flush=True,
            )
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

    approval_mode: Literal["prompt", "approve_all", "reject_all"] = manifest.runtime.approval_mode

    approval_policy = RunApprovalPolicy(
        mode=approval_mode,
        approval_callback=_prompt_approval_in_tui,
        return_permission_errors=True,
    )

    # Resolve file paths and determine effective model
    worker_paths, python_paths = resolve_manifest_paths(manifest, manifest_dir)
    effective_model = (
        manifest.entry.model
        or manifest.runtime.model
        or model_override
    )

    message_log_callback = None
    if log_verbosity >= 3:
        message_log_callback = _make_message_log_callback(sys.stderr)

    runtime = Runtime(
        cli_model=effective_model,
        run_approval_policy=approval_policy,
        max_depth=manifest.runtime.max_depth,
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
            turn_input = {"input": user_prompt}
            result, ctx = await run(
                manifest=manifest,
                manifest_dir=manifest_dir,
                input_data=turn_input,
                model_override=model_override,
                message_history=message_history,
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

    # Get initial prompt from input_data
    initial_prompt = input_data.get("input", "")
    if not initial_prompt:
        emit_error_event("No input prompt provided", "ValueError")
        return 1

    async def run_worker_in_background() -> int:
        """Run the worker and send events to the app."""
        history = await run_turn(initial_prompt, None)
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
    manifest: ProjectManifest,
    manifest_dir: Path,
    input_data: dict[str, Any],
    *,
    model_override: str | None,
    verbosity: int,
    backend: DisplayBackend | None,
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
            manifest=manifest,
            manifest_dir=manifest_dir,
            input_data=input_data,
            model_override=model_override,
            on_event=on_event,
            verbosity=verbosity,
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
    parser.add_argument(
        "manifest",
        help="Path to project manifest (JSON file)",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Prompt for the LLM (overrides manifest entry.input)",
    )
    parser.add_argument(
        "--input-json",
        dest="input_json",
        help="Input as inline JSON (overrides manifest entry.input)",
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

    args = parser.parse_args()

    # Validate mutually exclusive flags
    if args.json and args.tui:
        print("Cannot combine --json and --tui", file=sys.stderr)
        return 1
    if args.headless and args.tui:
        print("Cannot combine --headless and --tui", file=sys.stderr)
        return 1

    # Load and validate manifest
    try:
        manifest, manifest_dir = load_manifest(args.manifest)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1

    # Determine input data
    has_cli_input = args.prompt is not None or args.input_json is not None

    if has_cli_input and not manifest.allow_cli_input:
        print(
            "Error: CLI input not allowed by manifest (allow_cli_input is false)",
            file=sys.stderr,
        )
        return 1

    if args.prompt is not None and args.input_json is not None:
        print("Error: Cannot combine prompt argument and --input-json", file=sys.stderr)
        return 1

    # Build input_data from CLI or manifest
    input_data: dict[str, Any]
    if args.input_json is not None:
        try:
            input_data = json.loads(args.input_json)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --input-json: {e}", file=sys.stderr)
            return 1
        if not isinstance(input_data, dict):
            print("Error: --input-json must be a JSON object", file=sys.stderr)
            return 1
    elif args.prompt is not None:
        input_data = {"input": args.prompt}
    elif manifest.entry.input is not None:
        input_data = manifest.entry.input
    else:
        # Try reading from stdin if not a TTY
        if not sys.stdin.isatty():
            stdin_input = sys.stdin.read().strip()
            if stdin_input:
                input_data = {"input": stdin_input}
            else:
                print(
                    "Error: No input provided (use prompt argument, --input-json, or manifest entry.input)",
                    file=sys.stderr,
                )
                return 1
        else:
            print(
                "Error: No input provided (use prompt argument, --input-json, or manifest entry.input)",
                file=sys.stderr,
            )
            return 1

    # Get model from environment (manifest model takes precedence in run())
    model_override = os.environ.get(ENV_MODEL_VAR)

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
            manifest=manifest,
            manifest_dir=manifest_dir,
            input_data=input_data,
            model_override=model_override,
            verbosity=tui_verbosity,
            log_verbosity=args.verbose,
            chat=args.chat,
            debug=args.debug,
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
            manifest=manifest,
            manifest_dir=manifest_dir,
            input_data=input_data,
            model_override=model_override,
            verbosity=args.verbose,
            backend=backend,
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
