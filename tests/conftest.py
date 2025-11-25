"""Shared test fixtures and helpers for llm-do test suite.

This module provides common fixtures used across multiple test files.
See tests/README.md for testing patterns and best practices.
"""
import pytest
from pydantic_ai.models.test import TestModel

from tests.tool_calling_model import ToolCallingModel


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
        - Worker definitions and their tool integration
        - Output schema validation
        - Tool calling behavior

    Example:
        def test_worker_with_tools(test_model):
            result = run_worker(
                worker="my_worker",
                cli_model=test_model,
                ...
            )
            # Verifies tools are registered and output schema works

    See tests/README.md for when to use TestModel vs custom agent_runner.
    """
    return TestModel(seed=42)


@pytest.fixture
def tool_calling_model_cls():
    """Return the deterministic mock model used to exercise tool flows."""

    return ToolCallingModel
