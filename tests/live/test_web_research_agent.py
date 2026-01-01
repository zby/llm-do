"""Live tests for the web_research_agent example.

Tests multi-worker orchestration with web search and fetch tools.

Run:
    pytest tests/live/test_web_research_agent.py -v

Requirements:
    - ANTHROPIC_API_KEY
    - SERPAPI_API_KEY for web search functionality
"""

import asyncio
import json
from pathlib import Path

from .conftest import get_default_model, run_example, skip_no_anthropic, skip_no_serpapi


@skip_no_anthropic
@skip_no_serpapi
def test_web_research_orchestrator_full_workflow(
    web_research_agent_example, approve_all_callback
):
    """Test the full web research workflow.

    This is a comprehensive integration test that exercises:
    - Orchestrator coordination
    - Web search tool (via SerpAPI)
    - Multiple worker delegation (extractor, consolidator, reporter)
    - File writing (reports)
    """
    # Clean output directory to ensure we detect newly written files
    reports_dir = Path("reports")
    if reports_dir.exists():
        for f in reports_dir.glob("*.md"):
            f.unlink()
    reports_dir.mkdir(exist_ok=True)

    result = asyncio.run(
        run_example(
            web_research_agent_example,
            "Python 3.13 new features",
            model=get_default_model(),
            approval_callback=approve_all_callback,
        )
    )

    assert result is not None

    # Check that report files were written
    md_files = list(reports_dir.glob("*.md"))

    assert md_files, "Should have written a markdown report"


@skip_no_anthropic
def test_web_research_consolidator(web_research_agent_example, approve_all_callback):
    """Test the consolidator worker.

    The consolidator merges insights from multiple sources.
    This test doesn't require SerpAPI as we provide mock data.
    """
    # Provide mock insights for consolidation
    mock_insights = {
        "topic": "Python release highlights",
        "extractions": [
            {
                "url": "https://example.com/python-1",
                "title": "Python 3.12 Overview",
                "summary": "Summary of improvements and new syntax.",
                "main_points": [
                    "Improved error messages",
                    "New syntax features for type hints",
                ],
                "metrics": [],
                "pros": ["Clearer errors"],
                "cons": [],
                "quotes": [],
                "confidence": 0.7,
            },
            {
                "url": "https://example.com/python-2",
                "title": "Interpreter Performance",
                "summary": "Highlights on runtime improvements.",
                "main_points": [
                    "Interpreter performance improvements",
                    "New standard library modules",
                ],
                "metrics": [],
                "pros": ["Faster execution"],
                "cons": [],
                "quotes": [],
                "confidence": 0.65,
            },
        ],
    }

    result = asyncio.run(
        run_example(
            web_research_agent_example,
            json.dumps(mock_insights),
            entry_name="web_research_consolidator",
            model=get_default_model(),
            approval_callback=approve_all_callback,
        )
    )

    assert result is not None
