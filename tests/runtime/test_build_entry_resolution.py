from pathlib import Path

import pytest
from pydantic_ai.toolsets import FunctionToolset

from llm_do.ctx_runtime import WorkerEntry
from llm_do.ctx_runtime.cli import build_entry


EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


@pytest.mark.anyio
async def test_build_entry_resolves_nested_worker_toolsets() -> None:
    worker_files = [
        str(EXAMPLES_DIR / "web_research_agent" / "main.worker"),
        str(EXAMPLES_DIR / "web_research_agent" / "web_research_extractor.worker"),
        str(EXAMPLES_DIR / "web_research_agent" / "web_research_consolidator.worker"),
        str(EXAMPLES_DIR / "web_research_agent" / "web_research_reporter.worker"),
    ]
    python_files = [str(EXAMPLES_DIR / "web_research_agent" / "tools.py")]

    entry = await build_entry(worker_files, python_files, model="test-model")
    assert isinstance(entry, WorkerEntry)

    extractor = next(
        toolset
        for toolset in entry.toolsets
        if isinstance(toolset, WorkerEntry) and toolset.name == "web_research_extractor"
    )
    function_toolsets = [
        toolset for toolset in extractor.toolsets if isinstance(toolset, FunctionToolset)
    ]
    assert function_toolsets, "Expected extractor to include web_research_tools toolset"

    tool_names = {name for toolset in function_toolsets for name in toolset.tools}
    assert "fetch_page" in tool_names
