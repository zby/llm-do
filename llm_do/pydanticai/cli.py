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
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    TextPart,
    UserPromptPart,
    SystemPromptPart,
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

        result = run_worker(
            registry=registry,
            worker=worker_name,
            input_data=input_data,
            attachments=args.attachments,
            cli_model=args.cli_model,
            creation_defaults=creation_defaults,
            approval_callback=approval_callback,
        )

        # JSON output mode (for scripting/automation)
        if args.json:
            serialized = result.model_dump(mode="json")
            json.dump(serialized, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0

        # Default: Rich formatted output
        if result.messages:
            console.print("\n[bold white]═══ Message Exchange ═══[/bold white]\n")
            _display_messages(result.messages, console)
            console.print()

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
