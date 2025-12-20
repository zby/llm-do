"""Live tests for the web_searcher example.

Tests server-side web search tool integration.

Run:
    pytest tests/live/test_web_searcher.py -v

Note: This requires a model that supports server-side web search
(e.g., Anthropic Claude with web search enabled).
"""

import asyncio

import pytest

from llm_do import run_worker_async

from .conftest import skip_no_anthropic


@skip_no_anthropic
def test_web_searcher_current_events(web_searcher_registry, approve_all_controller):
    """Test that web_searcher can find current information.

    Note: Uses Anthropic directly since server-side web search
    is provider-specific.
    """
    result = asyncio.run(
        run_worker_async(
            registry=web_searcher_registry,
            worker="main",
            input_data="What is the current weather in New York City?",
            cli_model="anthropic:claude-haiku-4-5",
            approval_controller=approve_all_controller,
        )
    )

    assert result is not None
    assert result.output is not None
    # Should contain some weather-related information
    assert len(result.output) > 50


@skip_no_anthropic
def test_web_searcher_tech_news(web_searcher_registry, approve_all_controller):
    """Test that web_searcher can find tech news."""
    result = asyncio.run(
        run_worker_async(
            registry=web_searcher_registry,
            worker="main",
            input_data="What are the latest developments in AI?",
            cli_model="anthropic:claude-haiku-4-5",
            approval_controller=approve_all_controller,
        )
    )

    assert result is not None
    assert result.output is not None
    # Should contain substantial content about AI
    assert len(result.output) > 100
    # Should mention AI-related terms
    assert any(term in result.output.lower() for term in ["ai", "artificial intelligence", "model", "language"])
