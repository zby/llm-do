"""CLI entry point for running PydanticAI-style workers.

The CLI is intentionally lightweight and focused on production use cases.
It provides a simple interface for running workers with live LLM models.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

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
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from .base import (
    WorkerCreationDefaults,
    WorkerRegistry,
    run_worker,
    approve_all_callback,
    strict_mode_callback,
)


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


def _display_messages(messages: list[ModelMessage], console: Console) -> None:
    """Display LLM messages with rich formatting."""
    for msg in messages:
        if isinstance(msg, ModelRequest):
            # User/system input to the model
            console.print()

            if msg.instructions:
                console.print(Panel(
                    msg.instructions,
                    title="[bold cyan]System Instructions[/bold cyan]",
                    border_style="cyan",
                ))

            for part in msg.parts:
                if isinstance(part, UserPromptPart):
                    # Handle both string and list content (with attachments)
                    if isinstance(part.content, str):
                        display_content = part.content
                    else:
                        # part.content is a Sequence[UserContent] with text + attachments
                        text_parts = []
                        attachment_count = 0
                        for item in part.content:
                            if isinstance(item, str):
                                text_parts.append(item)
                            else:
                                # BinaryContent, ImageUrl, etc.
                                attachment_count += 1

                        display_content = "\n".join(text_parts)
                        if attachment_count:
                            display_content += f"\n\n[dim]+ {attachment_count} attachment(s)[/dim]"

                    console.print(Panel(
                        display_content,
                        title="[bold green]User Input[/bold green]",
                        border_style="green",
                    ))
                elif isinstance(part, SystemPromptPart):
                    console.print(Panel(
                        part.content,
                        title="[bold cyan]System Prompt[/bold cyan]",
                        border_style="cyan",
                    ))
                elif isinstance(part, ToolReturnPart):
                    # Tool result being sent back to model
                    tool_content = part.content
                    if isinstance(tool_content, str):
                        display_content = tool_content
                    else:
                        display_content = json.dumps(tool_content, indent=2)

                    console.print(Panel(
                        Syntax(display_content, "json", theme="monokai", line_numbers=False),
                        title=f"[bold yellow]Tool Result: {part.tool_name}[/bold yellow]",
                        border_style="yellow",
                    ))

        elif isinstance(msg, ModelResponse):
            # Model's response
            for part in msg.parts:
                if isinstance(part, TextPart):
                    console.print(Panel(
                        part.content,
                        title="[bold magenta]Model Response[/bold magenta]",
                        border_style="magenta",
                    ))
                elif isinstance(part, ToolCallPart):
                    # Model is calling a tool
                    args_json = json.dumps(part.args, indent=2)
                    console.print(Panel(
                        Syntax(args_json, "json", theme="monokai", line_numbers=False),
                        title=f"[bold blue]Tool Call: {part.tool_name}[/bold blue]",
                        border_style="blue",
                    ))


def _stringify_user_input(user_input: Any) -> str:
    """Convert arbitrary input data to displayable text."""

    if isinstance(user_input, str):
        return user_input
    return json.dumps(user_input, indent=2, sort_keys=True)


def _display_initial_request(
    *,
    definition: "WorkerDefinition",
    user_input: Any,
    attachments: Optional[list[str]],
    console: Console,
) -> None:
    """Render the outgoing message sent to the LLM before streaming starts."""

    prompt_text = _stringify_user_input(user_input)
    user_content: Any
    if attachments:
        user_content = [prompt_text]
        for attachment in attachments:
            placeholder = BinaryContent(
                data=b"",
                media_type="application/octet-stream",
                identifier=Path(attachment).name,
            )
            user_content.append(placeholder)
    else:
        user_content = prompt_text

    request = ModelRequest(
        parts=[UserPromptPart(content=user_content)],
        instructions=definition.instructions,
    )
    _display_messages([request], console)


def _build_streaming_callback(console: Console):
    """Create a callback that prints streaming events as they arrive."""

    def _format_jsonish(value: Any) -> str:
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, indent=2)
        except Exception:  # pragma: no cover - defensive
            return str(value)

    def _print_tool_call(worker: str, part: ToolCallPart) -> None:
        console.print()
        args_text = _format_jsonish(part.args)
        console.print(Panel(
            Syntax(args_text, "json", theme="monokai", line_numbers=False)
            if args_text.strip().startswith(("{", "["))
            else Text(args_text),
            title=f"[bold blue]{worker} ▷ Tool Call: {part.tool_name}[/bold blue]",
            border_style="blue",
        ))

    def _print_tool_result(worker: str, result: ToolReturnPart | RetryPromptPart) -> None:
        console.print()
        if isinstance(result, ToolReturnPart):
            payload = _format_jsonish(result.content)
            body = (
                Syntax(payload, "json", theme="monokai", line_numbers=False)
                if payload.strip().startswith(("{", "["))
                else Text(payload)
            )
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
            _display_initial_request(
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
            # Default: interactive approval (would need implementation)
            # For now, default to approve_all to match previous behavior
            approval_callback = approve_all_callback

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

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
