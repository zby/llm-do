"""Live tests for the orchestrating_tool example.

Tests a Python tool that orchestrates multiple agents internally.

Run:
    pytest tests/live/test_orchestrating_tool.py -v

Requirements:
    - ANTHROPIC_API_KEY (uses server-side web_search)
"""

import asyncio

from .conftest import get_default_model, run_example, skip_no_anthropic


@skip_no_anthropic
def test_orchestrating_tool_deep_research(
    orchestrating_tool_example,
    approve_all_callback,
):
    """Test the deep_research tool orchestrates multiple agents.

    The tool internally:
    1. Calls query_expander to generate search queries
    2. Calls searcher for each query (parallel)
    3. Calls synthesizer to combine findings

    This tests the "tools that orchestrate agents" pattern.
    """
    result = asyncio.run(
        run_example(
            orchestrating_tool_example,
            {"input": "What are the main differences between Python and Rust?"},
            model=get_default_model(),
            approval_callback=approve_all_callback,
            max_depth=5,  # Needs depth for nested agent calls
        )
    )

    assert result is not None
    # The result should be a synthesized answer mentioning both languages
    result_lower = result.lower()
    assert "python" in result_lower
    assert "rust" in result_lower
