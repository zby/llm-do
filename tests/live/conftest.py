"""Shared fixtures and configuration for live integration tests.

These tests make real API calls and require API keys to be set.
They are excluded from the default test run.

To run all live tests:
    pytest tests/live/ -v

To run specific example tests:
    pytest tests/live/test_greeter.py -v

Environment variables:
    ANTHROPIC_API_KEY - Required for most tests
    OPENAI_API_KEY - Alternative provider
    SERPAPI_API_KEY - Required for web_research_agent tests
"""

import os
import shutil
from pathlib import Path

import pytest

from llm_do import ApprovalController, WorkerRegistry


# Mark all tests in this directory as live tests
pytestmark = pytest.mark.live


def has_anthropic_key() -> bool:
    """Check if Anthropic API key is available."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def has_openai_key() -> bool:
    """Check if OpenAI API key is available."""
    return bool(os.environ.get("OPENAI_API_KEY"))


def has_serpapi_key() -> bool:
    """Check if SerpAPI key is available."""
    return bool(os.environ.get("SERPAPI_API_KEY"))


def has_any_llm_key() -> bool:
    """Check if any LLM provider API key is available."""
    return has_anthropic_key() or has_openai_key()


# Skip conditions
skip_no_anthropic = pytest.mark.skipif(
    not has_anthropic_key(),
    reason="ANTHROPIC_API_KEY not set"
)

skip_no_openai = pytest.mark.skipif(
    not has_openai_key(),
    reason="OPENAI_API_KEY not set"
)

skip_no_serpapi = pytest.mark.skipif(
    not has_serpapi_key(),
    reason="SERPAPI_API_KEY not set"
)

skip_no_llm = pytest.mark.skipif(
    not has_any_llm_key(),
    reason="No LLM API key set (need ANTHROPIC_API_KEY or OPENAI_API_KEY)"
)


def get_default_model() -> str:
    """Get the default model to use for tests.

    Prefers Anthropic Haiku for cost-effectiveness.
    Falls back to OpenAI if only OpenAI key is available.
    """
    if has_anthropic_key():
        return "anthropic:claude-haiku-4-5"
    elif has_openai_key():
        return "openai:gpt-4o-mini"
    else:
        raise ValueError("No LLM API key available")


@pytest.fixture
def default_model() -> str:
    """Fixture providing the default model for tests."""
    return get_default_model()


@pytest.fixture
def approve_all_controller() -> ApprovalController:
    """Approval controller that auto-approves everything."""
    return ApprovalController(mode="approve_all")


@pytest.fixture
def example_registry_factory(tmp_path, monkeypatch):
    """Factory fixture for creating registries from examples.

    Usage:
        def test_something(example_registry_factory):
            registry = example_registry_factory("greeter")
            # Now you can use the registry
    """
    def _create_registry(example_name: str) -> WorkerRegistry:
        source = Path(__file__).parent.parent.parent / "examples" / example_name
        if not source.exists():
            raise ValueError(f"Example not found: {example_name}")

        dest = tmp_path / example_name
        shutil.copytree(source, dest)

        # Change CWD to example directory so relative paths resolve correctly
        monkeypatch.chdir(dest)

        return WorkerRegistry(dest)

    return _create_registry


@pytest.fixture
def greeter_registry(example_registry_factory):
    """Registry for the greeter example."""
    return example_registry_factory("greeter")


@pytest.fixture
def calculator_registry(example_registry_factory):
    """Registry for the calculator example."""
    return example_registry_factory("calculator")


@pytest.fixture
def code_analyzer_registry(example_registry_factory):
    """Registry for the code_analyzer example."""
    return example_registry_factory("code_analyzer")


@pytest.fixture
def web_searcher_registry(example_registry_factory):
    """Registry for the web_searcher example."""
    return example_registry_factory("web_searcher")


@pytest.fixture
def pitchdeck_eval_registry(example_registry_factory):
    """Registry for the pitchdeck_eval example."""
    return example_registry_factory("pitchdeck_eval")


@pytest.fixture
def web_research_agent_registry(example_registry_factory):
    """Registry for the web_research_agent example."""
    return example_registry_factory("web_research_agent")


@pytest.fixture
def whiteboard_planner_registry(example_registry_factory):
    """Registry for the whiteboard_planner example."""
    return example_registry_factory("whiteboard_planner")
