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

from .conftest import skip_no_llm, skip_no_serpapi, has_serpapi_key, get_default_model


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
    json_files = list(reports_dir.glob("*.json"))

    # The orchestrator should write both markdown and JSON reports
    assert len(md_files) > 0, "Should have written a markdown report"

    # Check the markdown report has content
    md_content = md_files[0].read_text()
    assert len(md_content) > 200, "Report should have substantial content"


@skip_no_llm
@skip_no_serpapi
def test_web_research_extractor(web_research_agent_registry, approve_all_controller):
    """Test the extractor worker in isolation.

    The extractor fetches a single URL and extracts insights.
    """
    result = asyncio.run(
        run_worker_async(
            registry=web_research_agent_registry,
            worker="web_research_extractor",
            input_data="Extract key information from https://docs.python.org/3/whatsnew/3.12.html",
            cli_model=get_default_model(),
            approval_controller=approve_all_controller,
        )
    )

    assert result is not None
    assert result.output is not None
    # Should return structured insights about Python 3.12
    assert len(str(result.output)) > 100


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

    assert result is not None
    assert result.output is not None
    assert len(str(result.output)) > 50


@skip_no_llm
def test_web_research_reporter(web_research_agent_registry, approve_all_controller):
    """Test the reporter worker.

    The reporter produces formatted markdown output.
    This test doesn't require SerpAPI as we provide mock data.
    """
    mock_consolidated = """
    Key Findings:
    1. Python 3.12 has improved error messages
    2. New typing features were added
    3. Performance is better

    Sources:
    - docs.python.org
    - python.org/downloads
    """

    result = asyncio.run(
        run_worker_async(
            registry=web_research_agent_registry,
            worker="web_research_reporter",
            input_data=f"Create a report from:\n{mock_consolidated}",
            cli_model=get_default_model(),
            approval_controller=approve_all_controller,
        )
    )

    assert result is not None
    assert result.output is not None
    assert len(result.output) > 100
