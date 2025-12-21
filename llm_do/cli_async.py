"""Async CLI entry point for llm-do tools.

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
    run_tool_async,
)
from .config_overrides import apply_cli_overrides
from .tool_registry import ToolRegistry
from .ui.display import (
    DisplayBackend,
    HeadlessDisplayBackend,
    JsonDisplayBackend,
    RichDisplayBackend,
    TextualDisplayBackend,
)
from .ui.events import ApprovalRequestEvent, TextResponseEvent, UIEvent
from .ui.parser import parse_approval_request, parse_event


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
        description="Run an llm-do tool",
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
        "--tool",
        default="main",
        help="Tool name to run (defaults to 'main')",
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
        help="Model override (highest priority, overrides worker/project defaults)",
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
        help="Non-interactive mode with plain text output (no TUI, no colors)",
    )
    parser.add_argument(
        "--no-rich",
        action="store_true",
        default=False,
        help="Disable Rich formatting (plain text, no colors)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase output verbosity (use -v for progress, -vv for streaming)",
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


def _parse_oauth_args(argv: list[str]) -> argparse.Namespace:
    """Parse arguments for 'llm-do-oauth' command."""
    parser = argparse.ArgumentParser(
        prog="llm-do-oauth",
        description="Manage OAuth credentials",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login", help="Login with OAuth provider")
    login_parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic"],
        help="OAuth provider to use (default: anthropic)",
    )
    login_parser.add_argument(
        "--open-browser",
        action="store_true",
        default=False,
        help="Attempt to open the authorization URL in a browser",
    )

    logout_parser = subparsers.add_parser("logout", help="Logout and clear OAuth credentials")
    logout_parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic"],
        help="OAuth provider to clear (default: anthropic)",
    )

    status_parser = subparsers.add_parser("status", help="Show OAuth login status")
    status_parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic"],
        help="OAuth provider to check (default: anthropic)",
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
    print("\nRun your tool with:")
    print(f"  cd {project_path} && llm-do \"your message\"")

    return 0


async def run_oauth_cli(argv: list[str]) -> int:
    """Handle the OAuth CLI entrypoint."""
    import sys
    import webbrowser

    from .oauth import get_oauth_path, has_oauth_credentials, login_anthropic, remove_oauth_credentials

    args = _parse_oauth_args(argv)

    if args.command == "login":
        if args.provider != "anthropic":
            print(f"Unsupported OAuth provider: {args.provider}", file=sys.stderr)
            return 2

        def on_auth_url(url: str) -> None:
            print("Open this URL in your browser to authorize:")
            print(url)
            if args.open_browser:
                webbrowser.open(url)

        async def on_prompt_code() -> str:
            return input("Paste the authorization code (format: code#state): ").strip()

        try:
            await login_anthropic(on_auth_url, on_prompt_code)
        except Exception as exc:
            print(f"OAuth login failed: {exc}", file=sys.stderr)
            return 1

        print(f"Saved OAuth credentials to {get_oauth_path()}")
        return 0

    if args.command == "logout":
        if args.provider != "anthropic":
            print(f"Unsupported OAuth provider: {args.provider}", file=sys.stderr)
            return 2
        if not has_oauth_credentials(args.provider):
            print(f"No OAuth credentials found for {args.provider}")
            return 0
        remove_oauth_credentials(args.provider)
        print(f"Cleared OAuth credentials for {args.provider}")
        return 0

    if args.command == "status":
        if args.provider != "anthropic":
            print(f"Unsupported OAuth provider: {args.provider}", file=sys.stderr)
            return 2
        status = "logged in" if has_oauth_credentials(args.provider) else "not logged in"
        print(f"{args.provider}: {status}")
        return 0

    print(f"Unknown OAuth command: {args.command}", file=sys.stderr)
    return 2


# ---------------------------------------------------------------------------
# Event queue + message callback
# ---------------------------------------------------------------------------


def _queue_message_callback(queue: asyncio.Queue[UIEvent | None]) -> Callable[[list[Any]], None]:
    """Create a message callback that parses raw events and enqueues typed UIEvents.

    Parsing happens in the callback so the queue always contains typed events.
    """
    def _callback(events: list[Any]) -> None:
        for raw_event in events:
            ui_event = parse_event(raw_event)
            queue.put_nowait(ui_event)

    return _callback


async def _render_loop(
    queue: asyncio.Queue[UIEvent | None],
    backend: DisplayBackend,
) -> None:
    """Consume typed events from queue and render via backend."""
    await backend.start()
    try:
        while True:
            event = await queue.get()
            if event is None:
                queue.task_done()
                break

            backend.display(event)
            queue.task_done()
    finally:
        await backend.stop()


async def _run_tui_mode(args: argparse.Namespace) -> int:
    """Run the CLI in Textual TUI mode."""
    import io
    from .ui.app import LlmDoApp

    # Validate TUI requirements - if no TTY on stdout, fall back to headless mode
    if not sys.stdout.isatty():
        # Fall back to headless mode (Rich output to stderr, result to stdout)
        return await _run_headless_mode(args)

    if args.json:
        print("Cannot use TUI mode with --json", file=sys.stderr)
        return 1

    if args.approve_all and args.strict:
        print("Cannot use --approve-all and --strict together", file=sys.stderr)
        return 1

    # Set up queues for app communication (typed events!)
    event_queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    approval_queue: asyncio.Queue[ApprovalDecision] = asyncio.Queue()

    # Create backend that forwards typed events to app
    backend = TextualDisplayBackend(event_queue)

    # Create a buffer to capture output for display after TUI exits
    # Respect --no-rich flag for post-TUI logging
    output_buffer = io.StringIO()
    if args.no_rich:
        log_backend: DisplayBackend = HeadlessDisplayBackend(output_buffer, verbosity=args.verbose)
    else:
        log_backend = RichDisplayBackend(output_buffer, force_terminal=True, verbosity=args.verbose)

    # Container to capture result and exit code from background worker
    worker_result: list[Any] = []
    worker_exit_code: list[int] = [0]  # Use list to allow modification in nested function

    def _emit_error_event(message: str, *, error_type: str) -> None:
        from .ui.events import ErrorEvent

        error_event = ErrorEvent(
            worker="worker",
            message=message,
            error_type=error_type,
        )
        event_queue.put_nowait(error_event)
        # Also log to buffer for post-TUI display
        log_backend.display(error_event)
        event_queue.put_nowait(None)
        worker_exit_code[0] = 1

    async def run_worker_in_background() -> int:
        """Run the worker and send events to the app."""
        try:
            registry_root = args.dir or Path.cwd()
            tool_name = args.tool

            registry = WorkerRegistry(registry_root)
            tool_registry = ToolRegistry(registry)
            resolved = tool_registry.find_tool(tool_name)

            if args.config_overrides:
                if resolved.kind != "worker":
                    raise ValueError("Config overrides require a worker tool entry point.")
                definition = registry.load_definition(tool_name)
                definition = apply_cli_overrides(
                    definition,
                    set_overrides=args.config_overrides,
                )
                registry._definitions_cache = {tool_name: definition}

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
                    # Parse the approval request into a typed event and send to TUI
                    approval_event = parse_approval_request(request)
                    event_queue.put_nowait(approval_event)
                    return await approval_queue.get()

                approval_controller = ApprovalController(
                    mode="interactive",
                    approval_callback=tui_approval_callback,
                )

            # Create a callback that parses and forwards to both TUI and log buffer
            def combined_message_callback(raw_events: list[Any]) -> None:
                for raw_event in raw_events:
                    ui_event = parse_event(raw_event)
                    # Forward typed event to TUI
                    backend.display(ui_event)
                    # Also render to log buffer for terminal output after TUI exits
                    log_backend.display(ui_event)

            result = await run_tool_async(
                registry=registry,
                tool=tool_name,
                input_data=input_data,
                attachments=args.attachments,
                cli_model=args.cli_model,
                creation_defaults=creation_defaults,
                approval_controller=approval_controller,
                message_callback=combined_message_callback,
            )

            # Capture result for stdout output
            worker_result.append(result)

            # Signal completion
            event_queue.put_nowait(None)
            return 0

        except FileNotFoundError as e:
            _emit_error_event(f"Error: {e}", error_type=type(e).__name__)
            if args.debug:
                raise
            return 1
        except json.JSONDecodeError as e:
            _emit_error_event(f"Invalid JSON: {e}", error_type=type(e).__name__)
            if args.debug:
                raise
            return 1
        except ValueError as e:
            _emit_error_event(f"Error: {e}", error_type=type(e).__name__)
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
            _emit_error_event(message, error_type=type(e).__name__)
            if args.debug:
                raise
            return 1
        except (UnexpectedModelBehavior, UserError) as e:
            _emit_error_event(f"Error: {e}", error_type=type(e).__name__)
            if args.debug:
                raise
            return 1
        except KeyboardInterrupt:
            _emit_error_event("Aborted by user", error_type="KeyboardInterrupt")
            return 1
        except Exception as e:
            _emit_error_event(f"Unexpected error: {e}", error_type=type(e).__name__)
            if args.debug:
                raise
            return 1

    # Create the Textual app with worker coroutine
    app = LlmDoApp(event_queue, approval_queue, worker_coro=run_worker_in_background())

    # Run with mouse disabled to allow terminal text selection
    await app.run_async(mouse=False)

    # Print captured output to stderr (session log)
    captured_output = output_buffer.getvalue()
    if captured_output:
        print(captured_output, file=sys.stderr)

    # Print final result to stdout
    if worker_result:
        result = worker_result[0]
        if isinstance(result.output, str):
            print(result.output)
        else:
            print(json.dumps(result.output, indent=2))

    return worker_exit_code[0]


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
        tool_name = args.tool

        registry = WorkerRegistry(registry_root)
        tool_registry = ToolRegistry(registry)
        resolved = tool_registry.find_tool(tool_name)

        if args.config_overrides:
            if resolved.kind != "worker":
                raise ValueError("Config overrides require a worker tool entry point.")
            definition = registry.load_definition(tool_name)
            definition = apply_cli_overrides(
                definition,
                set_overrides=args.config_overrides,
            )
            registry._definitions_cache = {tool_name: definition}

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
        queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
        renderer = asyncio.create_task(_render_loop(queue, backend))
        message_callback = _queue_message_callback(queue)

        try:
            result = await run_tool_async(
                registry=registry,
                tool=tool_name,
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
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
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
        tool_name = args.tool

        registry = WorkerRegistry(registry_root)
        tool_registry = ToolRegistry(registry)
        resolved = tool_registry.find_tool(tool_name)

        if args.config_overrides:
            if resolved.kind != "worker":
                raise ValueError("Config overrides require a worker tool entry point.")
            definition = registry.load_definition(tool_name)
            definition = apply_cli_overrides(
                definition,
                set_overrides=args.config_overrides,
            )
            registry._definitions_cache = {tool_name: definition}

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
        elif sys.stdin.isatty():
            # Interactive approval via stdin when user is present
            async def stdin_approval_callback(request: ApprovalRequest) -> ApprovalDecision:
                print(f"\n[Approval Required] {request.tool_name}", file=sys.stderr)
                if request.description:
                    print(f"  {request.description}", file=sys.stderr)
                if request.tool_args:
                    args_str = json.dumps(request.tool_args, indent=2, default=str)
                    if len(args_str) > 300:
                        args_str = args_str[:300] + "..."
                    print(f"  Args: {args_str}", file=sys.stderr)
                print("  [a]pprove / [s]ession / [d]eny: ", end="", file=sys.stderr, flush=True)

                response = input().strip().lower()
                if response in ("a", "approve", "y", "yes", ""):
                    return ApprovalDecision(approved=True)
                elif response in ("s", "session"):
                    return ApprovalDecision(approved=True, remember="session")
                else:
                    return ApprovalDecision(approved=False, note="Rejected by user")

            approval_controller = ApprovalController(
                mode="interactive",
                approval_callback=stdin_approval_callback,
            )
        else:
            # No TTY on stdin, strict mode
            approval_controller = ApprovalController(mode="strict")

        # Choose backend: Rich by default, plain text if --no-rich or --headless
        use_plain = args.no_rich or args.headless
        if use_plain:
            backend: DisplayBackend = HeadlessDisplayBackend(verbosity=args.verbose)
        else:
            backend = RichDisplayBackend(force_terminal=True, verbosity=args.verbose)
        queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
        renderer = asyncio.create_task(_render_loop(queue, backend))
        message_callback = _queue_message_callback(queue)

        try:
            result = await run_tool_async(
                registry=registry,
                tool=tool_name,
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

        # Print final result to stdout (display output already went to stderr)
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
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
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


async def run_async_cli(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    # Validate mutually exclusive output modes
    if args.json and args.headless:
        print("Cannot combine --json and --headless", file=sys.stderr)
        return 1

    if args.json and not args.no_rich:
        # JSON mode implicitly disables Rich (machine-readable output)
        args.no_rich = True

    # Determine if we're in headless mode (explicit flag only)
    is_headless = args.headless

    # JSON mode
    if args.json:
        return await _run_json_mode(args)

    # Interactive TUI mode (default when TTY available)
    if not is_headless:
        return await _run_tui_mode(args)

    # Headless mode requires approval flags if stdin is not interactive
    if not args.approve_all and not args.strict and not sys.stdin.isatty():
        print(
            "Headless mode requires --approve-all or --strict for approval handling",
            file=sys.stderr,
        )
        return 1

    # Headless mode
    return await _run_headless_mode(args)


def oauth_main() -> int:
    """Entry point for the llm-do-oauth command."""
    return asyncio.run(run_oauth_cli(sys.argv[1:]))


def main() -> int:
    """Entry point for the llm-do command."""
    # Handle 'init' subcommand
    argv = sys.argv[1:]
    if argv and argv[0] == "init":
        return init_project(argv[1:])

    return asyncio.run(run_async_cli(argv))


if __name__ == "__main__":
    raise SystemExit(main())
