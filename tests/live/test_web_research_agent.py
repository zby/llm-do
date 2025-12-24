"""Live tests for the web_research_agent example.

Tests multi-worker orchestration with web search and fetch tools.

Run:
    pytest tests/live/test_web_research_agent.py -v

Requirements:
    - ANTHROPIC_API_KEY or OPENAI_API_KEY
    - SERPAPI_API_KEY for web search functionality
"""

import asyncio
from pathlib import Path

import pytest

from llm_do import run_worker_async

from .conftest import skip_no_llm, skip_no_serpapi, get_default_model


@skip_no_llm
@skip_no_serpapi
def test_web_research_orchestrator_full_workflow(
    web_research_agent_registry, approve_all_controller
):
    """Test the full web research workflow.

    This is a comprehensive integration test that exercises:
    - Orchestrator coordination
    - Web search tool (via SerpAPI)
    - Multiple worker delegation (extractor, consolidator, reporter)
    - File writing (reports)
    """
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    result = asyncio.run(
        run_worker_async(
            registry=web_research_agent_registry,
            worker="web_research_orchestrator",
            input_data="Python 3.13 new features",
            cli_model=get_default_model(),
            approval_controller=approve_all_controller,
        )
    )

    assert result is not None

    # Check that report files were written
    md_files = list(reports_dir.glob("*.md"))

    assert md_files, "Should have written a markdown report"


@skip_no_llm
def test_web_research_consolidator(web_research_agent_registry, approve_all_controller):
    """Test the consolidator worker.

    The consolidator merges insights from multiple sources.
    This test doesn't require SerpAPI as we provide mock data.
    """
    # Provide mock insights for consolidation
    mock_insights = """
    Source 1 findings:
    - Python 3.12 introduces improved error messages
    - New syntax features for type hints

    Source 2 findings:
    - Performance improvements in the interpreter
    - New standard library modules
    """

    result = asyncio.run(
        run_worker_async(
            registry=web_research_agent_registry,
            worker="web_research_consolidator",
            input_data=f"Consolidate these research findings:\n{mock_insights}",
            cli_model=get_default_model(),
            approval_controller=approve_all_controller,
        )
    )

    assert result and result.output is not None
