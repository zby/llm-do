"""CLI entry point for running PydanticAI-style workers.

The CLI is intentionally lightweight and focused on production use cases.
It provides a simple interface for running workers with live LLM models.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UserError
from pydantic_ai.messages import (
    BinaryContent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    PartEndEvent,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
    SystemPromptPart,
    RetryPromptPart,
)
from rich.console import Console, Group
from rich.json import JSON
from rich.panel import Panel
from rich.text import Text

from .base import (
    WorkerCreationDefaults,
    WorkerRegistry,
    run_worker,
)
from pydantic_ai_blocking_approval import (
    ApprovalController,
    ApprovalDecision,
    ApprovalRequest,
)
from .config_overrides import apply_cli_overrides
from .cli_display import (
    display_worker_request,
    display_worker_status,
    display_streaming_model_response,
    display_streaming_tool_call,
    display_streaming_tool_result,
    render_json_or_text,
)


def _is_interactive_terminal() -> bool:
    """Return True when both stdin and stdout are connected to a TTY."""

    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def _load_jsonish(value: str, *, allow_plain_text: bool = False) -> Any:
    """Load JSON from an inline string or filesystem path.

    The helper mirrors the permissive behavior of many CLIs: if the argument
    points to an existing file, the file is read as JSON. Otherwise the value
    itself is parsed as JSON. This keeps the interface small while supporting
    both ad-hoc invocations and scripted runs.
    """

    candidate = Path(value)
    source: str
    if candidate.exists():
        source = candidate.read_text(encoding="utf-8")
    else:
        source = value

    try:
        return json.loads(source)
    except json.JSONDecodeError:
        if allow_plain_text:
            return source
        raise


def _load_creation_defaults(path: Optional[str]) -> WorkerCreationDefaults:
    if not path:
        return WorkerCreationDefaults()
    data = _load_jsonish(path)
    return WorkerCreationDefaults.model_validate(data)


def _build_interactive_approval_controller(
    console: Console,
    *,
    worker_name: str,
) -> ApprovalController:
    """Return an ApprovalController that prompts the user before running gated tools."""

    def _prompt_choice() -> str:
        response = console.input(
            "[bold cyan]Approval choice [a/s/d/q][/bold cyan]: "
        )
        return response.strip().lower()

    def _callback(request: ApprovalRequest) -> ApprovalDecision:
        reason_text = request.description or "Approval required"
        body = Group(
            Text(f"Reason: {reason_text}\n", style="bold red"),
            Text("Tool args:", style="bold"),
            render_json_or_text(request.tool_args),
        )
        console.print()
        console.print(
            Panel(
                body,
                title=f"[bold red]{worker_name} ▷ Tool approval: {request.tool_name}[/bold red]",
                border_style="red",
            )
        )

        options = Text()
        options.append("[a] Approve and continue\n", style="green")
        options.append("[s] Approve for remainder of session\n", style="green")
        options.append("[d] Deny and abort\n", style="red")
        options.append("[q] Quit run", style="red")
        console.print(Panel(options, title="Approval choices", border_style="cyan"))

        while True:
            choice = _prompt_choice()
            if choice in {"", "a"}:
                return ApprovalDecision(approved=True)
            if choice == "s":
                return ApprovalDecision(approved=True, remember="session")
            if choice == "d":
                return ApprovalDecision(
                    approved=False, note="Rejected via interactive CLI"
                )
            if choice == "q":
                raise KeyboardInterrupt

            console.print("Unknown choice. Use a/s/d/q.", style="yellow")

    return ApprovalController(mode="interactive", approval_callback=_callback)


def _build_streaming_callback(console: Console):
    """Create a callback that prints streaming events as they arrive."""

    def _callback(events: list[Any]) -> None:
        for payload in events:
            if isinstance(payload, dict):
                worker = str(payload.get("worker", "worker"))
                preview = payload.get("initial_request")
                if preview is not None:
                    display_worker_request(console, worker, preview)
                    continue
                status = payload.get("status")
                if status is not None:
                    display_worker_status(console, worker, status)
                    continue
                event = payload.get("event")
            else:
                worker = "worker"
                event = payload

            if event is None:
                continue

            if isinstance(event, PartEndEvent):
                part = event.part
                if isinstance(part, TextPart):
                    display_streaming_model_response(console, worker, part.content)
            elif isinstance(event, FunctionToolCallEvent):
                display_streaming_tool_call(console, worker, event.part)
            elif isinstance(event, FunctionToolResultEvent):
                display_streaming_tool_result(console, worker, event.result)

        console.file.flush()

    return _callback



def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a PydanticAI worker")
    parser.add_argument(
        "worker",
        help="Worker name or path to .yaml file (e.g., 'greeter' or 'examples/greeter.yaml')",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="Input message (plain text). Use --input for JSON instead.",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="Path to the worker registry root (defaults to current working directory)",
    )
    parser.add_argument(
        "--input",
        dest="input_json",
        default=None,
        help="JSON payload or path to JSON file for worker input (alternative to plain message)",
    )
    parser.add_argument(
        "--model",
        dest="cli_model",
        default=None,
        help="Model to use (e.g., anthropic:claude-sonnet-4-20250514, openai:gpt-4o). Required if worker has no model.",
    )
    parser.add_argument(
        "--creation-defaults",
        dest="creation_defaults_path",
        default=None,
        help="Optional JSON file describing default settings for worker creation",
    )
    parser.add_argument(
        "--attachments",
        nargs="*",
        default=None,
        help="Attachment file paths passed to the worker",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output JSON instead of rich formatted display (for scripting/automation)",
    )
    parser.add_argument(
        "--approve-all",
        action="store_true",
        default=False,
        help="Auto-approve all tool calls without prompting (use with caution)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Reject all non-pre-approved tools (deny-by-default security mode)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Show full stack traces on errors (for debugging)",
    )
    parser.add_argument(
        "--set",
        action="append",
        dest="config_overrides",
        metavar="KEY=VALUE",
        default=None,
        help="Override worker config field (e.g., --set model=openai:gpt-4o). "
             "Supports dot notation for nested fields (e.g., --set sandbox.network_enabled=false). "
             "Can be specified multiple times.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    console = Console()
    prompt_console = console if not args.json else Console(stderr=True)

    try:
        # Determine worker name and registry
        worker_path = Path(args.worker)
        if worker_path.exists() and worker_path.suffix in {".yaml", ".yml"}:
            # Worker is a file path
            worker_name = worker_path.stem
        else:
            # Worker is a name
            worker_name = args.worker

        # Registry defaults to current working directory
        if args.registry is None:
            registry_root = Path.cwd()
        else:
            registry_root = args.registry

        registry = WorkerRegistry(registry_root)

        # Load worker definition
        definition = registry.load_definition(worker_name)

        # Apply CLI overrides if provided
        if args.config_overrides:
            try:
                definition = apply_cli_overrides(
                    definition,
                    set_overrides=args.config_overrides,
                )
                # Show what was overridden in debug mode
                if args.debug and not args.json:
                    console.print(
                        f"[dim]Applied {len(args.config_overrides)} --set override(s)[/dim]"
                    )
            except ValueError as e:
                print(f"Configuration override error: {e}", file=sys.stderr)
                return 1

            # Temporarily inject overridden definition into registry
            # This allows run_worker to use our modified version
            registry._definitions_cache = {worker_name: definition}

        # Determine input data
        if args.input_json is not None:
            # Use JSON input if provided
            input_data = _load_jsonish(args.input_json, allow_plain_text=True)
        elif args.message is not None:
            # Use plain text message
            input_data = args.message
        else:
            # Default to empty input
            input_data = {}

        creation_defaults = _load_creation_defaults(args.creation_defaults_path)

        # Show the outgoing request immediately in rich mode
        if not args.json:
            console.print("\n[bold white]═══ Message Exchange ═══[/bold white]\n")

        # Determine approval controller based on flags
        if args.approve_all and args.strict:
            print("Error: Cannot use --approve-all and --strict together", file=sys.stderr)
            return 1
        elif args.approve_all:
            approval_controller = ApprovalController(mode="approve_all")
        elif args.strict:
            approval_controller = ApprovalController(mode="strict")
        else:
            if not _is_interactive_terminal():
                print(
                    "Error: interactive approvals require a TTY. Use --approve-all or --strict for non-interactive runs.",
                    file=sys.stderr,
                )
                return 1
            approval_controller = _build_interactive_approval_controller(
                prompt_console, worker_name=worker_name
            )

        streaming_callback = None if args.json else _build_streaming_callback(console)

        result = run_worker(
            registry=registry,
            worker=worker_name,
            input_data=input_data,
            attachments=args.attachments,
            cli_model=args.cli_model,
            creation_defaults=creation_defaults,
            approval_controller=approval_controller,
            message_callback=streaming_callback,
        )

        # JSON output mode (for scripting/automation)
        if args.json:
            serialized = result.model_dump(mode="json")
            json.dump(serialized, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0

        # Display final output in a nice panel
        console.print(Panel(
            json.dumps(result.output, indent=2) if not isinstance(result.output, str) else result.output,
            title="[bold green]Final Output[/bold green]",
            border_style="green",
        ))
        console.print()
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1

    except PermissionError as e:
        print(f"Permission denied: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1

    except ValueError as e:
        print(f"Invalid input: {e}", file=sys.stderr)
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


if __name__ == "__main__":
    raise SystemExit(main())
