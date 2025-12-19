"""Async CLI entry point for llm-do workers.

This module provides the main async CLI implementation with native async
approval callbacks and event-driven display rendering.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UserError
from pydantic_ai_blocking_approval import ApprovalController, ApprovalDecision, ApprovalRequest

from .base import (
    WorkerCreationDefaults,
    WorkerRegistry,
    run_worker_async,
)
from .config_overrides import apply_cli_overrides
from .ui.display import (
    CLIEvent,
    DisplayBackend,
    JsonDisplayBackend,
    TextualDisplayBackend,
)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _is_json_file(value: str) -> bool:
    candidate = Path(value)
    return candidate.exists() and candidate.is_file()


def _load_jsonish(value: str, *, allow_plain_text: bool = False) -> Any:
    if _is_json_file(value):
        source = Path(value).read_text(encoding="utf-8")
    else:
        source = value

    try:
        return json.loads(source)
    except json.JSONDecodeError:
        if allow_plain_text:
            return source
        raise


def _load_creation_defaults(value: Optional[str]) -> WorkerCreationDefaults:
    if not value:
        return WorkerCreationDefaults()
    data = _load_jsonish(value)
    return WorkerCreationDefaults.model_validate(data)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a PydanticAI worker",
        epilog="Use 'llm-do init' to create a new project.",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="Plain-text input. Use --input for JSON payloads.",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Registry root directory (defaults to cwd)",
    )
    parser.add_argument(
        "--worker",
        default="main",
        help="Worker name to run (defaults to 'main')",
    )
    parser.add_argument(
        "--input",
        dest="input_json",
        default=None,
        help="JSON payload or path to JSON file",
    )
    parser.add_argument(
        "--model",
        dest="cli_model",
        default=None,
        help="Fallback model if worker does not specify one",
    )
    parser.add_argument(
        "--creation-defaults",
        dest="creation_defaults_path",
        default=None,
        help="Path to JSON defaults for new workers",
    )
    parser.add_argument(
        "--attachments",
        nargs="*",
        default=None,
        help="Attachment file paths",
    )
    parser.add_argument(
        "--approve-all",
        action="store_true",
        default=False,
        help="Auto-approve tools (default behavior)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Reject tools unless pre-approved",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit machine-readable JSON output",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Force non-interactive mode (plain text output)",
    )
    parser.add_argument(
        "--set",
        action="append",
        dest="config_overrides",
        metavar="KEY=VALUE",
        help="Override fields on the worker definition",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Show full stack traces on errors",
    )
    return parser.parse_args(argv)


def _parse_init_args(argv: list[str]) -> argparse.Namespace:
    """Parse arguments for 'llm-do init' command."""
    parser = argparse.ArgumentParser(
        prog="llm-do init",
        description="Initialize a new llm-do project",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to initialize (default: current directory)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Project/worker name (default: directory name)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Default model for the worker (e.g., anthropic:claude-haiku-4-5)",
    )
    return parser.parse_args(argv)


def init_project(argv: list[str]) -> int:
    """Initialize a new llm-do project with a sample worker."""
    args = _parse_init_args(argv)

    project_path = Path(args.path).resolve()

    if not project_path.exists():
        project_path.mkdir(parents=True)
        print(f"Created directory: {project_path}")

    project_name = args.name or project_path.name

    main_worker = project_path / "main.worker"
    if main_worker.exists():
        print(f"Worker already exists: {main_worker}", file=sys.stderr)
        return 1

    front_matter = [
        "---",
        "name: main",
        f"description: A helpful assistant for {project_name}",
    ]
    if args.model:
        front_matter.append(f"model: {args.model}")
    front_matter.append("---")

    sample_worker_content = "\n".join(front_matter) + f"""
You are a helpful assistant for the {project_name} project.

Respond to the user's request.
"""
    main_worker.write_text(sample_worker_content)
    print(f"Created: {main_worker}")
    print("\nProject initialized!")
    print("\nRun your worker with:")
    print(f"  cd {project_path} && llm-do \"your message\"")

    return 0


# ---------------------------------------------------------------------------
# Event queue + message callback
# ---------------------------------------------------------------------------


def _queue_message_callback(queue: "asyncio.Queue[Any]") -> Callable[[list[Any]], None]:
    """Create a message callback that enqueues events directly.

    Since the worker now runs in the same event loop, we can put items
    directly on the queue without threadsafe wrappers.
    """
    def _callback(events: list[Any]) -> None:
        for event in events:
            queue.put_nowait(CLIEvent(kind="runtime_event", payload=event))

    return _callback


async def _render_loop(
    queue: "asyncio.Queue[Any]",
    backend: DisplayBackend,
) -> None:
    await backend.start()
    try:
        while True:
            payload = await queue.get()
            if payload is None:
                break

            if isinstance(payload, CLIEvent):
                backend.handle_event(payload)
            queue.task_done()
    finally:
        await backend.stop()


async def _run_tui_mode(args: argparse.Namespace) -> int:
    """Run the CLI in Textual TUI mode."""
    from .ui.app import LlmDoApp

    # Validate TUI requirements
    if not sys.stdout.isatty():
        print("TUI mode requires a TTY; use --json or default Rich mode", file=sys.stderr)
        return 1

    if args.json:
        print("Cannot use --tui with --json", file=sys.stderr)
        return 1

    # Set up queues for app communication
    event_queue: asyncio.Queue[Any] = asyncio.Queue()
    approval_queue: asyncio.Queue[ApprovalDecision] = asyncio.Queue()

    # Create backend that forwards to app
    backend = TextualDisplayBackend(event_queue)

    async def run_worker_in_background() -> int:
        """Run the worker and send events to the app."""
        try:
            registry_root = args.dir or Path.cwd()
            worker_name = args.worker

            registry = WorkerRegistry(registry_root)
            definition = registry.load_definition(worker_name)

            if args.config_overrides:
                definition = apply_cli_overrides(
                    definition,
                    set_overrides=args.config_overrides,
                )
                registry._definitions_cache = {worker_name: definition}

            if args.input_json is not None:
                input_data = _load_jsonish(args.input_json, allow_plain_text=True)
            elif args.message is not None:
                input_data = args.message
            else:
                input_data = {}

            creation_defaults = _load_creation_defaults(args.creation_defaults_path)

            # Set up approval controller
            if args.approve_all:
                approval_controller = ApprovalController(mode="approve_all")
            elif args.strict:
                approval_controller = ApprovalController(mode="strict")
            else:
                # TUI approval callback
                async def tui_approval_callback(request: ApprovalRequest) -> ApprovalDecision:
                    event_queue.put_nowait(CLIEvent(kind="approval_request", payload=request))
                    return await approval_queue.get()

                approval_controller = ApprovalController(
                    mode="interactive",
                    approval_callback=tui_approval_callback,
                )

            message_callback = (
                _queue_message_callback_direct(event_queue)
                if backend.wants_runtime_events
                else None
            )

            result = await run_worker_async(
                registry=registry,
                worker=worker_name,
                input_data=input_data,
                attachments=args.attachments,
                cli_model=args.cli_model,
                creation_defaults=creation_defaults,
                approval_controller=approval_controller,
                message_callback=message_callback,
            )

            # Signal completion
            event_queue.put_nowait(None)
            return 0

        except Exception as e:
            event_queue.put_nowait(CLIEvent(kind="runtime_event", payload=f"Error: {e}"))
            event_queue.put_nowait(None)
            if args.debug:
                raise
            return 1

    # Create the Textual app with worker coroutine
    app = LlmDoApp(event_queue, approval_queue, worker_coro=run_worker_in_background())

    # Run with mouse disabled to allow terminal text selection
    await app.run_async(mouse=False)
    return 0


def _queue_message_callback_direct(queue: asyncio.Queue[Any]) -> Callable[[list[Any]], None]:
    """Create a message callback that puts CLIEvents directly on the queue."""
    def _callback(events: list[Any]) -> None:
        for event in events:
            queue.put_nowait(CLIEvent(kind="runtime_event", payload=event))
    return _callback


async def _run_json_mode(args: argparse.Namespace) -> int:
    """Run the CLI in JSON output mode."""
    # JSON mode requires approval flags
    if not args.approve_all and not args.strict:
        print(
            "JSON mode requires --approve-all or --strict for approval handling",
            file=sys.stderr,
        )
        return 1

    if args.approve_all and args.strict:
        print("Cannot use --approve-all and --strict together", file=sys.stderr)
        return 1

    try:
        registry_root = args.dir or Path.cwd()
        worker_name = args.worker

        registry = WorkerRegistry(registry_root)
        definition = registry.load_definition(worker_name)

        if args.config_overrides:
            definition = apply_cli_overrides(
                definition,
                set_overrides=args.config_overrides,
            )
            registry._definitions_cache = {worker_name: definition}

        if args.input_json is not None:
            input_data = _load_jsonish(args.input_json, allow_plain_text=True)
        elif args.message is not None:
            input_data = args.message
        else:
            input_data = {}

        creation_defaults = _load_creation_defaults(args.creation_defaults_path)

        # Set up approval controller
        if args.approve_all:
            approval_controller = ApprovalController(mode="approve_all")
        else:
            approval_controller = ApprovalController(mode="strict")

        # JSON backend writes events to stderr
        backend = JsonDisplayBackend()
        queue: asyncio.Queue[Any] = asyncio.Queue()
        renderer = asyncio.create_task(_render_loop(queue, backend))
        message_callback = _queue_message_callback(queue) if backend.wants_runtime_events else None

        try:
            result = await run_worker_async(
                registry=registry,
                worker=worker_name,
                input_data=input_data,
                attachments=args.attachments,
                cli_model=args.cli_model,
                creation_defaults=creation_defaults,
                approval_controller=approval_controller,
                message_callback=message_callback,
            )
        finally:
            await queue.put(None)
            await renderer

        # Output final result to stdout
        serialized = result.model_dump(mode="json")
        json.dump(serialized, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1
    except ModelHTTPError as e:
        print(f"Model API error (status {e.status_code}): {e.model_name}", file=sys.stderr)
        if e.body and isinstance(e.body, dict):
            error_info = e.body.get("error", {})
            if isinstance(error_info, dict):
                msg = error_info.get("message", "")
                if msg:
                    print(f"  {msg}", file=sys.stderr)
        if args.debug:
            raise
        return 1
    except (UnexpectedModelBehavior, UserError) as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1
    except KeyboardInterrupt:
        print("Aborted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1


async def _run_headless_mode(args: argparse.Namespace) -> int:
    """Run the CLI in headless mode (plain text output, no interactivity)."""
    if args.approve_all and args.strict:
        print("Cannot use --approve-all and --strict together", file=sys.stderr)
        return 1

    try:
        registry_root = args.dir or Path.cwd()
        worker_name = args.worker

        registry = WorkerRegistry(registry_root)
        definition = registry.load_definition(worker_name)

        if args.config_overrides:
            definition = apply_cli_overrides(
                definition,
                set_overrides=args.config_overrides,
            )
            registry._definitions_cache = {worker_name: definition}

        if args.input_json is not None:
            input_data = _load_jsonish(args.input_json, allow_plain_text=True)
        elif args.message is not None:
            input_data = args.message
        else:
            input_data = {}

        creation_defaults = _load_creation_defaults(args.creation_defaults_path)

        # Set up approval controller (no interactive mode in headless)
        if args.approve_all:
            approval_controller = ApprovalController(mode="approve_all")
        else:
            approval_controller = ApprovalController(mode="strict")

        # No message callback in headless mode - just run silently
        result = await run_worker_async(
            registry=registry,
            worker=worker_name,
            input_data=input_data,
            attachments=args.attachments,
            cli_model=args.cli_model,
            creation_defaults=creation_defaults,
            approval_controller=approval_controller,
            message_callback=None,
        )

        # Print final output
        if isinstance(result.output, str):
            print(result.output)
        else:
            print(json.dumps(result.output, indent=2))
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1
    except ModelHTTPError as e:
        print(f"Model API error (status {e.status_code}): {e.model_name}", file=sys.stderr)
        if e.body and isinstance(e.body, dict):
            error_info = e.body.get("error", {})
            if isinstance(error_info, dict):
                msg = error_info.get("message", "")
                if msg:
                    print(f"  {msg}", file=sys.stderr)
        if args.debug:
            raise
        return 1
    except (UnexpectedModelBehavior, UserError) as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1
    except KeyboardInterrupt:
        print("Aborted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1


def _is_interactive() -> bool:
    """Check if we're running in an interactive terminal."""
    return sys.stdin.isatty() and sys.stdout.isatty()


async def run_async_cli(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    # Validate mutually exclusive output modes
    if args.json and args.headless:
        print("Cannot combine --json and --headless", file=sys.stderr)
        return 1

    # Determine if we're in headless mode (explicit or auto-detected)
    is_headless = args.headless or not _is_interactive()

    # JSON mode
    if args.json:
        return await _run_json_mode(args)

    # Interactive TUI mode (default when TTY available)
    if not is_headless:
        return await _run_tui_mode(args)

    # Headless mode requires approval flags
    if not args.approve_all and not args.strict:
        print(
            "Headless mode requires --approve-all or --strict for approval handling",
            file=sys.stderr,
        )
        return 1

    # Headless mode - minimal output
    return await _run_headless_mode(args)


def main() -> int:
    """Entry point for the llm-do command."""
    # Handle 'init' subcommand
    argv = sys.argv[1:]
    if argv and argv[0] == "init":
        return init_project(argv[1:])

    return asyncio.run(run_async_cli(argv))


if __name__ == "__main__":
    raise SystemExit(main())
