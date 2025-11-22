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
    ApprovalCallback,
    ApprovalDecision,
    WorkerCreationDefaults,
    WorkerRegistry,
    run_worker,
    approve_all_callback,
    strict_mode_callback,
)
from .cli_display import (
    display_initial_request,
    display_messages,
    render_json_or_text,
    stringify_user_input,
)


def _is_interactive_terminal() -> bool:
    """Return True when both stdin and stdout are connected to a TTY."""

    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def _load_jsonish(value: str) -> Any:
    """Load JSON from an inline string or filesystem path.

    The helper mirrors the permissive behavior of many CLIs: if the argument
    points to an existing file, the file is read as JSON. Otherwise the value
    itself is parsed as JSON. This keeps the interface small while supporting
    both ad-hoc invocations and scripted runs.
    """

    candidate = Path(value)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(value)


def _load_creation_defaults(path: Optional[str]) -> WorkerCreationDefaults:
    if not path:
        return WorkerCreationDefaults()
    data = _load_jsonish(path)
    return WorkerCreationDefaults.model_validate(data)


def _build_interactive_approval_callback(
    console: Console,
    *,
    worker_name: str,
) -> ApprovalCallback:
    """Return a callback that prompts the user before running gated tools."""

    def _prompt_choice() -> str:
        response = console.input(
            "[bold cyan]Approval choice [a/s/d/q][/bold cyan]: "
        )
        return response.strip().lower()

    def _callback(
        tool_name: str, payload: Mapping[str, Any], reason: Optional[str]
    ):
        reason_text = reason or "Approval required"
        body = Group(
            Text(f"Reason: {reason_text}\n", style="bold red"),
            Text("Payload:", style="bold"),
            render_json_or_text(payload),
        )
        console.print()
        console.print(
            Panel(
                body,
                title=f"[bold red]{worker_name} ▷ Tool approval: {tool_name}[/bold red]",
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
                return ApprovalDecision(approved=True, approve_for_session=True)
            if choice == "d":
                return ApprovalDecision(
                    approved=False, note="Rejected via interactive CLI"
                )
            if choice == "q":
                raise KeyboardInterrupt

            console.print("Unknown choice. Use a/s/d/q.", style="yellow")

    return _callback


def _build_streaming_callback(console: Console):
    """Create a callback that prints streaming events as they arrive."""

    def _print_tool_call(worker: str, part: ToolCallPart) -> None:
        console.print()
        console.print(Panel(
            render_json_or_text(part.args),
            title=f"[bold blue]{worker} ▷ Tool Call: {part.tool_name}[/bold blue]",
            border_style="blue",
        ))

    def _print_tool_result(worker: str, result: ToolReturnPart | RetryPromptPart) -> None:
        console.print()
        if isinstance(result, ToolReturnPart):
            body = render_json_or_text(result.content)
            title = f"[bold yellow]{worker} ◁ Tool Result: {result.tool_name}[/bold yellow]"
        else:
            body = Text(result.instructions or "Retry requested", style="yellow")
            title = f"[bold yellow]{worker} ◁ Tool Retry[/bold yellow]"
        console.print(Panel(body, title=title, border_style="yellow"))

    def _print_model_response(worker: str, text: str) -> None:
        if not text.strip():
            return
        console.print()
        console.print(Panel(
            text,
            title=f"[bold magenta]{worker} ▷ Model Response[/bold magenta]",
            border_style="magenta",
        ))

    def _callback(events: list[Any]) -> None:
        for payload in events:
            if isinstance(payload, dict):
                worker = str(payload.get("worker", "worker"))
                event = payload.get("event")
            else:
                worker = "worker"
                event = payload

            if event is None:
                continue

            if isinstance(event, PartEndEvent):
                part = event.part
                if isinstance(part, TextPart):
                    _print_model_response(worker, part.content)
            elif isinstance(event, FunctionToolCallEvent):
                _print_tool_call(worker, event.part)
            elif isinstance(event, FunctionToolResultEvent):
                _print_tool_result(worker, event.result)

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

        # Determine input data
        if args.input_json is not None:
            # Use JSON input if provided
            input_data = _load_jsonish(args.input_json)
        elif args.message is not None:
            # Use plain text message
            input_data = args.message
        else:
            # Default to empty input
            input_data = {}

        creation_defaults = _load_creation_defaults(args.creation_defaults_path)

        # Show the outgoing request immediately in rich mode
        preview_definition = None
        if not args.json:
            preview_definition = registry.load_definition(worker_name)
            console.print("\n[bold white]═══ Message Exchange ═══[/bold white]\n")
            display_initial_request(
                definition=preview_definition,
                user_input=input_data,
                attachments=args.attachments,
                console=console,
            )

        # Determine approval callback based on flags
        if args.approve_all and args.strict:
            print("Error: Cannot use --approve-all and --strict together", file=sys.stderr)
            return 1
        elif args.approve_all:
            approval_callback = approve_all_callback
        elif args.strict:
            approval_callback = strict_mode_callback
        else:
            if not _is_interactive_terminal():
                print(
                    "Error: interactive approvals require a TTY. Use --approve-all or --strict for non-interactive runs.",
                    file=sys.stderr,
                )
                return 1
            approval_callback = _build_interactive_approval_callback(
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
            approval_callback=approval_callback,
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
