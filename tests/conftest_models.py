"""Test model utilities for integration testing without live LLM calls.

This module provides:
- ScenarioModel: A FunctionModel that responds based on prompt patterns
- Fixtures for common testing scenarios
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel


@dataclass
class ToolCall:
    """A tool call to be made by the model."""
    name: str
    args: dict[str, Any]

    def to_part(self, call_id: str = "test_call_1") -> ToolCallPart:
        import json
        return ToolCallPart(
            tool_name=self.name,
            args=json.dumps(self.args),
            tool_call_id=call_id,
        )


@dataclass
class Scenario:
    """A test scenario mapping prompts to responses."""
    pattern: str | re.Pattern[str]
    """Regex pattern to match against the user prompt."""

    response: str | None = None
    """Text response to return."""

    tool_calls: list[ToolCall] = field(default_factory=list)
    """Tool calls to make before responding."""

    def matches(self, prompt: str) -> bool:
        if isinstance(self.pattern, str):
            return bool(re.search(self.pattern, prompt, re.IGNORECASE))
        return bool(self.pattern.search(prompt))

    def to_response(self, call_id_prefix: str = "call") -> ModelResponse:
        parts = []

        # Add tool calls first
        for i, tc in enumerate(self.tool_calls):
            parts.append(tc.to_part(f"{call_id_prefix}_{i}"))

        # Add text response if no tool calls or if explicitly set
        if self.response is not None:
            parts.append(TextPart(content=self.response))
        elif not self.tool_calls:
            parts.append(TextPart(content="I understand."))

        return ModelResponse(parts=parts)


def extract_user_prompt(messages: list[ModelMessage]) -> str:
    """Extract the most recent user prompt from messages."""
    for msg in reversed(messages):
        for part in msg.parts:
            if isinstance(part, UserPromptPart):
                return part.content
    return ""


def has_tool_results(messages: list[ModelMessage]) -> bool:
    """Check if there are tool results in the messages (meaning tools were executed)."""
    from pydantic_ai.messages import ToolReturnPart
    for msg in messages:
        for part in msg.parts:
            if isinstance(part, ToolReturnPart):
                return True
    return False


def get_last_tool_result(messages: list[ModelMessage]) -> Any:
    """Get the content of the last tool result."""
    from pydantic_ai.messages import ToolReturnPart
    for msg in reversed(messages):
        for part in reversed(msg.parts):
            if isinstance(part, ToolReturnPart):
                return part.content
    return None


def create_scenario_model(
    scenarios: list[Scenario],
    default_response: str = "I don't know how to help with that.",
) -> FunctionModel:
    """Create a FunctionModel that responds based on scenarios.

    Args:
        scenarios: List of scenarios to match against prompts
        default_response: Response when no scenario matches

    Returns:
        FunctionModel configured with the scenarios
    """
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        # If tools have been executed, return the result as text
        if has_tool_results(messages):
            result = get_last_tool_result(messages)
            return ModelResponse(parts=[TextPart(content=f"Result: {result}")])

        prompt = extract_user_prompt(messages)

        for scenario in scenarios:
            if scenario.matches(prompt):
                return scenario.to_response()

        return ModelResponse(parts=[TextPart(content=default_response)])

    return FunctionModel(respond)


# Common calculator scenarios
CALCULATOR_SCENARIOS = [
    Scenario(
        pattern=r"multiply\s+(\d+)\s+(?:by|and|x|\*)\s+(\d+)",
        tool_calls=[ToolCall("multiply", {"a": 0, "b": 0})],  # Args filled dynamically
    ),
    Scenario(
        pattern=r"add\s+(\d+)\s+(?:and|plus|\+)\s+(\d+)",
        tool_calls=[ToolCall("add", {"a": 0, "b": 0})],
    ),
    Scenario(
        pattern=r"factorial\s+(?:of\s+)?(\d+)",
        tool_calls=[ToolCall("factorial", {"n": 0})],
    ),
    Scenario(
        pattern=r"fibonacci\s+(?:of\s+)?(\d+)",
        tool_calls=[ToolCall("fibonacci", {"n": 0})],
    ),
]


def create_calculator_model() -> FunctionModel:
    """Create a model that responds like a calculator assistant.

    This model:
    - Parses arithmetic prompts and calls appropriate tools
    - Extracts numbers from prompts and passes them as arguments
    - Returns tool results as text after execution
    """
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        # If tools have been executed, return the result as text
        if has_tool_results(messages):
            result = get_last_tool_result(messages)
            return ModelResponse(parts=[TextPart(content=f"The result is {result}")])

        prompt = extract_user_prompt(messages)

        # Try to match multiply pattern
        if match := re.search(r"multiply\s+(\d+)\s+(?:by|and|x|\*)\s+(\d+)", prompt, re.I):
            a, b = int(match.group(1)), int(match.group(2))
            return ModelResponse(parts=[
                ToolCall("multiply", {"a": a, "b": b}).to_part()
            ])

        # Try to match add pattern
        if match := re.search(r"add\s+(\d+)\s+(?:and|plus|\+)\s+(\d+)", prompt, re.I):
            a, b = int(match.group(1)), int(match.group(2))
            return ModelResponse(parts=[
                ToolCall("add", {"a": a, "b": b}).to_part()
            ])

        # Try to match factorial pattern
        if match := re.search(r"factorial\s+(?:of\s+)?(\d+)", prompt, re.I):
            n = int(match.group(1))
            return ModelResponse(parts=[
                ToolCall("factorial", {"n": n}).to_part()
            ])

        # Try to match fibonacci pattern
        if match := re.search(r"fibonacci\s+(?:of\s+)?(\d+)", prompt, re.I):
            n = int(match.group(1))
            return ModelResponse(parts=[
                ToolCall("fibonacci", {"n": n}).to_part()
            ])

        return ModelResponse(parts=[
            TextPart(content="I can help with: multiply, add, factorial, fibonacci")
        ])

    return FunctionModel(respond)


# Multi-turn conversation model
@dataclass
class ConversationModel:
    """A model that tracks conversation state for multi-turn testing."""

    turns: list[Callable[[str, list[ModelMessage], AgentInfo], ModelResponse]]
    """List of response functions, one per turn."""

    current_turn: int = 0

    def respond(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = extract_user_prompt(messages)

        if self.current_turn < len(self.turns):
            response = self.turns[self.current_turn](prompt, messages, info)
            self.current_turn += 1
            return response

        return ModelResponse(parts=[TextPart(content="Conversation ended.")])

    def to_model(self) -> FunctionModel:
        return FunctionModel(self.respond)

    def reset(self) -> None:
        self.current_turn = 0
