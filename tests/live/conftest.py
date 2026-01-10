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
from typing import Any, Callable

import pytest

from llm_do.runtime import WorkerRuntime, build_invocable_registry
from llm_do.runtime.approval import (
    RunApprovalPolicy,
    make_headless_approval_callback,
)

# Mark all tests in this directory as live tests
pytestmark = pytest.mark.live
EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


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
def approve_all_callback() -> Callable[[Any], Any]:
    """Approval callback that auto-approves everything."""
    return make_headless_approval_callback(approve_all=True, reject_all=False)


@pytest.fixture
def example_dir_factory(tmp_path, monkeypatch):
    """Factory fixture for creating temp copies of examples.

    Usage:
        def test_something(example_dir_factory):
            example_dir = example_dir_factory("greeter")
            # Now you can use the example directory
    """
    def _create_example_dir(example_name: str) -> Path:
        source = EXAMPLES_DIR / example_name
        if not source.exists():
            raise ValueError(f"Example not found: {example_name}")

        dest = tmp_path / example_name
        shutil.copytree(source, dest)

        # Change CWD to example directory so relative paths resolve correctly
        monkeypatch.chdir(dest)

        return dest

    return _create_example_dir


def _collect_example_files(example_dir: Path) -> tuple[list[str], list[str]]:
    worker_files = sorted(str(path) for path in example_dir.glob("*.worker"))
    python_files = sorted(str(path) for path in example_dir.glob("tools.py"))
    return worker_files, python_files


async def run_example(
    example_dir: Path,
    input_data: Any,
    *,
    entry_name: str = "main",
    model: str | None = None,
    approval_callback: Callable[[Any], Any] | None = None,
    max_depth: int | None = None,
    on_event: Callable[[Any], Any] | None = None,
    verbosity: int = 0,
) -> Any:
    """Build and run an example entry with approvals wired."""
    worker_files, python_files = _collect_example_files(example_dir)
    registry = await build_invocable_registry(
        worker_files,
        python_files,
        entry_name=entry_name,
        entry_model_override=model,
    )
    entry = registry.get(entry_name)

    approval_policy = RunApprovalPolicy(
        mode="approve_all" if approval_callback is None else "prompt",
        approval_callback=approval_callback,
    )

    ctx = WorkerRuntime.from_entry(
        entry,
        model=model,
        run_approval_policy=approval_policy,
        max_depth=max_depth if max_depth is not None else 5,
        on_event=on_event,
        verbosity=verbosity,
    )
    return await ctx.run(entry, input_data)


@pytest.fixture
def greeter_example(example_dir_factory):
    """Example directory for greeter."""
    return example_dir_factory("greeter")


@pytest.fixture
def calculator_example(example_dir_factory):
    """Example directory for calculator."""
    return example_dir_factory("calculator")


@pytest.fixture
def code_analyzer_example(example_dir_factory):
    """Example directory for code_analyzer."""
    return example_dir_factory("code_analyzer")


@pytest.fixture
def web_searcher_example(example_dir_factory):
    """Example directory for web_searcher."""
    return example_dir_factory("web_searcher")


@pytest.fixture
def pitchdeck_eval_example(example_dir_factory):
    """Example directory for pitchdeck_eval."""
    return example_dir_factory("pitchdeck_eval")


@pytest.fixture
def web_research_agent_example(example_dir_factory):
    """Example directory for web_research_agent."""
    return example_dir_factory("web_research_agent")


@pytest.fixture
def whiteboard_planner_example(example_dir_factory):
    """Example directory for whiteboard_planner."""
    return example_dir_factory("whiteboard_planner")


@pytest.fixture
def recursive_summarizer_example(example_dir_factory):
    """Example directory for recursive_summarizer."""
    return example_dir_factory("recursive_summarizer")
