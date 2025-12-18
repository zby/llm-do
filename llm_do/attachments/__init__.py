"""Attachment types and policies for worker delegation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Protocol, Sequence, Union

from pydantic import BaseModel, Field, field_validator

__all__ = [
    "AttachmentInput",
    "AttachmentPayload",
    "AttachmentPolicy",
    "ApprovalRunner",
]


@dataclass
class AttachmentPayload:
    """Attachment path plus a display-friendly label."""

    path: Path
    display_name: str


AttachmentInput = Union[str, Path, AttachmentPayload]


class AttachmentPolicy(BaseModel):
    """Constraints for inbound attachments."""

    max_attachments: int = 4
    max_total_bytes: int = 10_000_000
    allowed_suffixes: List[str] = Field(default_factory=list)
    denied_suffixes: List[str] = Field(default_factory=list)

    @field_validator("max_attachments")
    @classmethod
    def _positive_max_attachments(cls, value: int) -> int:
        if value < 0:
            raise ValueError("max_attachments must be non-negative")
        return value

    @field_validator("max_total_bytes")
    @classmethod
    def _positive_max_total_bytes(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("max_total_bytes must be positive")
        return value

    @field_validator("allowed_suffixes", "denied_suffixes")
    @classmethod
    def _lower_suffixes(cls, value: List[str]) -> List[str]:
        return [suffix.lower() for suffix in value]

    def validate_paths(self, attachments: Sequence[Path]) -> None:
        """Validate attachment paths against policy constraints.

        Args:
            attachments: List of attachment paths to validate

        Raises:
            ValueError: If policy constraints are violated
        """
        if len(attachments) > self.max_attachments:
            raise ValueError("Too many attachments provided")
        total = 0
        for path in attachments:
            suffix = path.suffix.lower()
            if self.allowed_suffixes and suffix not in self.allowed_suffixes:
                raise ValueError(f"Attachment suffix '{suffix}' not allowed")
            if self.denied_suffixes and suffix in self.denied_suffixes:
                raise ValueError(f"Attachment suffix '{suffix}' is denied")
            size = path.stat().st_size
            total += size
            if total > self.max_total_bytes:
                raise ValueError("Attachments exceed max_total_bytes")


class ApprovalRunner(Protocol):
    """Protocol for approval checking (used by tools)."""

    def maybe_run(
        self,
        tool_name: str,
        tool_kwargs: dict[str, Any],
        func: Callable[[], Any],
    ) -> Any:
        """Run func if approved, or prompt user for approval.

        Args:
            tool_name: Name of the tool being invoked
            tool_kwargs: Arguments passed to the tool
            func: Function to execute if approved

        Returns:
            Result of func() if approved

        Raises:
            PermissionError: If approval is denied
        """
        ...
