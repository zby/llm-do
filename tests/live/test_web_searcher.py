"""Live tests for the web_searcher example.

Tests server-side web search tool integration.

Run:
    pytest tests/live/test_web_searcher.py -v

Note: This requires a model that supports server-side web search
(e.g., Anthropic Claude with web search enabled).
"""

import asyncio

from llm_do.runtime import WorkerInput

from .conftest import run_example, skip_no_anthropic


@skip_no_anthropic
def test_web_searcher_current_events(web_searcher_example, approve_all_callback):
    """Test that web_searcher can find current information.

    Note: Uses Anthropic directly since server-side web search
    is provider-specific.
    """
    result = asyncio.run(
        run_example(
            web_searcher_example,
            WorkerInput(input="What is the current weather in New York City?"),
            model="anthropic:claude-haiku-4-5",
            approval_callback=approve_all_callback,
        )
    )

    assert result is not None
    # Should contain some weather-related information
    assert len(result) > 50


@skip_no_anthropic
def test_web_searcher_tech_news(web_searcher_example, approve_all_callback):
    """Test that web_searcher can find tech news."""
    result = asyncio.run(
        run_example(
            web_searcher_example,
            WorkerInput(input="What are the latest developments in AI?"),
            model="anthropic:claude-haiku-4-5",
            approval_callback=approve_all_callback,
        )
    )

    assert result is not None
    # Should contain substantial content about AI
    assert len(result) > 100
    # Should mention AI-related terms
    assert any(term in result.lower() for term in ["ai", "artificial intelligence", "model", "language"])
