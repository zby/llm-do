"""Worker input models and prompt specs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


@dataclass(frozen=True, slots=True)
class PromptSpec:
    """Rendered prompt metadata derived from worker args."""

    text: str
    attachments: tuple[str, ...] = ()

    def _normalized_text(self) -> str:
        """Return display-safe text for prompts with no user input."""
        # TODO: Revisit normalization rules for empty prompts.
        return self.text if self.text.strip() else "(no input)"


class WorkerArgs(BaseModel):
    """Base class for worker input models."""

    def prompt_spec(self) -> PromptSpec:
        raise NotImplementedError("WorkerArgs subclasses must implement prompt_spec().")


class WorkerInput(WorkerArgs):
    """Default worker input schema."""

    input: str
    attachments: list[str] = Field(default_factory=list)

    def prompt_spec(self) -> PromptSpec:
        return PromptSpec(text=self.input, attachments=tuple(self.attachments))


def ensure_worker_args(
    schema_in: type[WorkerArgs] | None,
    input_data: Any,
) -> WorkerArgs:
    """Normalize raw input into a WorkerArgs instance."""
    schema = schema_in or WorkerInput
    if not issubclass(schema, WorkerArgs):
        raise TypeError(f"schema_in must subclass WorkerArgs; got {schema}")

    if isinstance(input_data, (str, bytes, bytearray)):
        raise TypeError(
            f"Worker inputs must be dict or WorkerArgs; got {type(input_data)}"
        )

    if isinstance(input_data, WorkerArgs):
        if isinstance(input_data, schema):
            return input_data
        input_data = input_data.model_dump()
    elif isinstance(input_data, BaseModel):
        raise TypeError(
            f"Worker inputs must subclass WorkerArgs; got {type(input_data)}"
        )

    args = schema.model_validate(input_data)
    if not isinstance(args, WorkerArgs):
        raise TypeError(f"schema_in did not produce WorkerArgs; got {type(args)}")
    return args
