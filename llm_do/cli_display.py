"""Rich console display utilities for llm-do CLI.

Provides rendering functions for LLM messages, user input, and structured data.
All functions use Rich for terminal formatting.
"""
from __future__ import annotations

from typing import Any, Mapping

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.text import Text


def render_json_or_text(value: Any) -> JSON | Text:
    """Render value as Rich JSON or Text with fallback for edge cases."""
    if isinstance(value, str):
        return Text(value)

    try:
        return JSON.from_data(value)
    except (TypeError, ValueError):
        # Fallback for non-serializable objects (should rarely happen)
        return Text(repr(value), style="dim")


def display_messages(messages: list[ModelMessage], console: Console) -> None:
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
                    console.print(Panel(
                        render_json_or_text(part.content),
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
                    console.print(Panel(
                        render_json_or_text(part.args),
                        title=f"[bold blue]Tool Call: {part.tool_name}[/bold blue]",
                        border_style="blue",
                    ))


def display_streaming_tool_call(console: Console, worker: str, part: ToolCallPart) -> None:
    """Display a tool call during streaming execution."""
    console.print()
    console.print(Panel(
        render_json_or_text(part.args),
        title=f"[bold blue]{worker} ▷ Tool Call: {part.tool_name}[/bold blue]",
        border_style="blue",
    ))


def display_streaming_tool_result(
    console: Console, worker: str, result: ToolReturnPart | RetryPromptPart
) -> None:
    """Display a tool result during streaming execution."""
    console.print()
    if isinstance(result, ToolReturnPart):
        body = render_json_or_text(result.content)
        title = f"[bold yellow]{worker} ◁ Tool Result: {result.tool_name}[/bold yellow]"
    else:
        # RetryPromptPart uses 'content' field
        content = result.content if isinstance(result.content, str) else str(result.content)
        body = Text(content or "Retry requested", style="yellow")
        title = f"[bold yellow]{worker} ◁ Tool Retry[/bold yellow]"
    console.print(Panel(body, title=title, border_style="yellow"))


def display_streaming_model_response(console: Console, worker: str, text: str) -> None:
    """Display a model response during streaming execution."""
    if not text.strip():
        return
    console.print()
    console.print(Panel(
        text,
        title=f"[bold magenta]{worker} ▷ Model Response[/bold magenta]",
        border_style="magenta",
    ))


def display_worker_status(console: Console, worker: str, status: Mapping[str, Any]) -> None:
    """Display status updates emitted by the runtime (e.g., model call start/end)."""

    phase = status.get("phase")
    state = status.get("state")
    model_name = status.get("model")
    duration = status.get("duration_sec")

    if phase == "model_request":
        if state == "start":
            message = f"Calling {model_name or 'model'}..."
        elif state == "end":
            if duration is not None:
                message = f"{model_name or 'Model'} finished in {duration:.2f}s"
            else:
                message = f"{model_name or 'Model'} finished"
        else:
            message = f"Model state: {state or 'unknown'}"
        body: JSON | Text = Text(message, style="cyan")
    else:
        body = render_json_or_text(status)

    console.print()
    console.print(Panel(
        body,
        title=f"[bold blue]{worker} ▷ Status[/bold blue]",
        border_style="blue",
    ))


def display_worker_request(
    console: Console,
    worker: str,
    preview: Mapping[str, Any],
) -> None:
    """Display the initial request sent to a worker (instructions + user input)."""

    console.print()
    instructions = preview.get("instructions") or ""
    if instructions.strip():
        console.print(
            Panel(
                instructions,
                title=f"[bold cyan]{worker} ▷ System Instructions[/bold cyan]",
                border_style="cyan",
            )
        )

    user_input = preview.get("user_input") or ""
    attachments = preview.get("attachments") or []
    body_sections: list[str] = []
    if user_input.strip():
        body_sections.append(user_input)
    if attachments:
        attachment_lines = "\n".join(f"- {name}" for name in attachments)
        body_sections.append(f"[dim]Attachments:\n{attachment_lines}[/dim]")

    if not body_sections:
        body_sections.append("[dim](no user input)[/dim]")

    console.print(
        Panel(
            "\n\n".join(body_sections),
            title=f"[bold green]{worker} ▷ User Input[/bold green]",
            border_style="green",
        )
    )
