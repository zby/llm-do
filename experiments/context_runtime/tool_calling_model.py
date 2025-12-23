"""Shared mock model that emits a predefined sequence of tool calls."""
from __future__ import annotations

from typing import Any

from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models import Model


class ToolCallingModel(Model):
    """Mock model used in tests to enforce deterministic tool call flows."""

    def __init__(self, tool_calls: list[dict[str, Any]] | dict[str, Any] | None = None):
        """Configure the sequence of tool calls the model should emit."""
        super().__init__()
        if isinstance(tool_calls, dict):
            tool_calls = tool_calls.get("tool_calls", [])
        self.tool_calls = tool_calls or []
        self.call_count = 0

    @property
    def model_name(self) -> str:
        return "tool-calling-mock"

    @property
    def system(self) -> str:
        return "test"

    async def request(self, messages, model_settings, model_request_parameters):
        self.call_count += 1

        runtime_calls = None
        if model_settings:
            runtime_calls = model_settings.get("tool_calls")
        tool_calls = runtime_calls if runtime_calls is not None else self.tool_calls

        has_tool_returns = any(
            isinstance(msg, ModelRequest)
            and any(isinstance(part, ToolReturnPart) for part in msg.parts)
            for msg in messages
        )

        if not has_tool_returns and tool_calls:
            parts = []
            for i, call in enumerate(tool_calls):
                parts.append(
                    ToolCallPart(
                        tool_name=call["name"],
                        args=call["args"],
                        tool_call_id=f"call_{i}",
                    )
                )
            return ModelResponse(parts=parts, model_name=self.model_name)

        return ModelResponse(
            parts=[TextPart(content="Task completed")],
            model_name=self.model_name,
        )
