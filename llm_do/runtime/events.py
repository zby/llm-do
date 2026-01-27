"""Runtime events emitted by the core execution layer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic_ai.messages import AgentStreamEvent


@dataclass(frozen=True, slots=True)
class UserMessageEvent:
    """System event emitted for user-submitted messages."""

    content: str = ""
    event_kind: Literal["user_message"] = "user_message"


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """Envelope for runtime callbacks (raw PydanticAI + system events)."""

    worker: str  # agent name
    depth: int
    event: AgentStreamEvent | UserMessageEvent
