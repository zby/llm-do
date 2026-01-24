"""Shared test fixtures and helpers for llm-do test suite.

This module provides common fixtures used across multiple test files.
See tests/README.md for testing patterns and best practices.
"""
import asyncio.base_events
from unittest.mock import patch

import pytest
from pydantic_ai.models.test import TestModel

from llm_do.models import LLM_DO_MODEL_ENV
from tests.tool_calling_model import ToolCallingModel


def _quiet_exception_handler(loop, context):
    """Custom exception handler that suppresses 'Task exception was never retrieved'.

    PydanticAI creates async tasks for tool calls. When a tool raises an exception
    (e.g., PermissionError from approval denial), the task's exception may not be
    "retrieved" before garbage collection, causing asyncio to print a warning.

    This is expected behavior during tests - the exception IS properly raised to
    the test, it just isn't retrieved via task.result() or task.exception().
    """
    message = context.get("message", "")
    # Check if this is the "Task exception was never retrieved" message
    if "exception was never retrieved" in message:
        # Suppress by not calling the default handler
        return
    # For other exceptions, use the default behavior
    loop.default_exception_handler(context)


@pytest.fixture(scope="session", autouse=True)
def suppress_task_exception_warnings():
    """Suppress 'Task exception was never retrieved' warnings during tests.

    PydanticAI uses asyncio.run() which creates new event loops, so we need to
    patch the BaseEventLoop class to install our handler on all new loops.
    """
    original_init = asyncio.base_events.BaseEventLoop.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.set_exception_handler(_quiet_exception_handler)

    with patch.object(asyncio.base_events.BaseEventLoop, "__init__", patched_init):
        yield


@pytest.fixture(autouse=True)
def default_model_env(monkeypatch):
    """Set a default model for tests that construct workers without explicit models."""
    monkeypatch.setenv(LLM_DO_MODEL_ENV, "test")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: tests that hit real APIs",
    )
    config.addinivalue_line(
        "markers",
        "custom_deps: tests that require optional/custom dependencies",
    )


@pytest.fixture
def test_model():
    """PydanticAI's TestModel for deterministic testing without API calls.

    TestModel provides canned responses that exercise the full agent flow
    including tool calling and structured output validation, but without
    making actual LLM API calls.

    Configuration options:
        - TestModel() - returns empty string by default
        - TestModel(custom_result_text="...") - returns specific text
        - TestModel(seed=42) - deterministic pseudo-random responses

    Use this fixture when testing:
        - Agent definitions and their tool integration
        - Output schema validation
        - Tool calling behavior

    Example:
        def test_agent_with_tools(test_model):
            agent = AgentSpec(name="my_agent", instructions="...", model=test_model)
            async def main(input_data, runtime):
                return await runtime.call_agent(agent, input_data)
            entry = EntrySpec(name="main", main=main)
            result, _ctx = asyncio.run(Runtime().run_entry(entry, {"input": "..."}))
            # Verifies tools are registered and output schema works

    See tests/README.md for when to use TestModel vs custom agent_runner.
    """
    return TestModel(seed=42)


@pytest.fixture
def tool_calling_model_cls():
    """Return the deterministic mock model used to exercise tool flows."""

    return ToolCallingModel
