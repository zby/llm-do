"""Worker input models and prompt message types."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel
from pydantic_ai.messages import BinaryContent, UserContent


class Attachment:
    """Lazy file attachment - stores path, renders to BinaryContent on demand."""

    __slots__ = ("path",)

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def __repr__(self) -> str:
        return f"Attachment({self.path!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Attachment):
            return self.path == other.path
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.path)

    def render(self, base_path: Path | None = None) -> BinaryContent:
        """Resolve path and load file as BinaryContent."""
        resolved = self.path.expanduser()
        if not resolved.is_absolute() and base_path is not None:
            resolved = base_path / resolved
        resolved = resolved.resolve()

        if not resolved.exists():
            raise FileNotFoundError(f"Attachment not found: {resolved}")

        media_type, _ = mimetypes.guess_type(str(resolved))
        return BinaryContent(
            data=resolved.read_bytes(),
            media_type=media_type or "application/octet-stream",
        )


# Type aliases for prompt content
PromptContent = str | Attachment
PromptMessages = Sequence[PromptContent]


def _normalize_text(text: str) -> str:
    """Normalize empty/whitespace text to a placeholder."""
    return text if text.strip() else "(no input)"


def render_prompt(
    messages: PromptMessages,
    base_path: Path | None = None,
) -> str | list[UserContent]:
    """Convert lazy prompt messages to LLM-ready format."""
    if len(messages) == 1 and isinstance(messages[0], str):
        return _normalize_text(messages[0])

    rendered: list[UserContent] = []
    for part in messages:
        if isinstance(part, str):
            rendered.append(_normalize_text(part))
        elif isinstance(part, Attachment):
            rendered.append(part.render(base_path))
        else:
            raise TypeError(f"Unsupported prompt content type: {type(part)}")
    return rendered


def get_display_text(messages: PromptMessages) -> str:
    """Extract display-safe text from prompt messages."""
    text_parts = [p for p in messages if isinstance(p, str)]
    if not text_parts:
        return "(no input)"
    text = " ".join(text_parts)
    return text if text.strip() else "(no input)"


def has_attachments(messages: PromptMessages) -> bool:
    """Check if messages contain any attachments."""
    return any(isinstance(p, Attachment) for p in messages)


class WorkerArgs(BaseModel):
    """Base class for structured worker input models.

    Use this when workers need structured input beyond simple text/attachments.
    """

    def prompt_messages(self) -> list[PromptContent]:
        """Return prompt content as a list of text/attachment parts."""
        raise NotImplementedError(
            "WorkerArgs subclasses must implement prompt_messages()."
        )


class WorkerInput(WorkerArgs):
    """Default worker input schema with text and optional attachments.

    This is provided for backwards compatibility. For simple cases,
    you can pass a string or list[str | Attachment] directly.
    """

    input: str
    attachments: list[str] = []

    def prompt_messages(self) -> list[PromptContent]:
        parts: list[PromptContent] = [self.input]
        parts.extend(Attachment(p) for p in self.attachments)
        return parts


def normalize_input(
    schema_in: type[WorkerArgs] | None,
    input_data: Any,
) -> tuple[WorkerArgs | None, list[PromptContent]]:
    """Normalize raw input into a message list, optionally with structured args.

    Returns:
        Tuple of (structured_args, messages). structured_args is None for
        simple string or list inputs.
    """
    # Direct string -> single-element list
    if isinstance(input_data, str):
        return None, [input_data]

    # Already a message list
    if isinstance(input_data, list):
        # Validate contents
        for item in input_data:
            if not isinstance(item, (str, Attachment)):
                raise TypeError(
                    f"Message list items must be str or Attachment; got {type(item)}"
                )
        return None, input_data

    # Structured WorkerArgs instance
    if isinstance(input_data, WorkerArgs):
        if schema_in is not None and not isinstance(input_data, schema_in):
            raise TypeError(
                f"Expected {schema_in.__name__}; got {type(input_data).__name__}"
            )
        return input_data, input_data.prompt_messages()

    # Dict -> validate with schema (or use WorkerInput as fallback)
    if isinstance(input_data, dict):
        schema = schema_in if schema_in is not None else WorkerInput
        args = schema.model_validate(input_data)
        return args, args.prompt_messages()

    # Other BaseModel (not WorkerArgs)
    if isinstance(input_data, BaseModel):
        raise TypeError(
            f"Structured inputs must subclass WorkerArgs; got {type(input_data)}"
        )

    raise TypeError(
        f"Worker input must be str, list[str | Attachment], dict, or WorkerArgs; "
        f"got {type(input_data)}"
    )
