from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from llm_do import WorkerDefinition, WorkerRegistry, run_tool_async
from llm_do.tool_registry import ToolRegistry


def test_tool_registry_resolves_code_tool_without_worker(tmp_path: Path) -> None:
    tools_py = tmp_path / "tools.py"
    tools_py.write_text(
        "def main(input: str) -> str:\n"
        "    return input\n"
    )

    registry = WorkerRegistry(tmp_path)
    tool_registry = ToolRegistry(registry)

    tool = tool_registry.find_tool("main")

    assert tool.kind == "code"
    assert tool.source_path == tools_py
    assert tool.handler("ok") == "ok"


def test_tool_registry_detects_name_collision(tmp_path: Path) -> None:
    tools_py = tmp_path / "tools.py"
    tools_py.write_text(
        "def main(input: str) -> str:\n"
        "    return input\n"
    )

    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))
    tool_registry = ToolRegistry(registry)

    with pytest.raises(ValueError, match="tools\\.py::main and main\\.worker"):
        tool_registry.find_tool("main")


def test_run_tool_async_code_entry_calls_worker(tmp_path: Path) -> None:
    tools_py = tmp_path / "tools.py"
    tools_py.write_text(
        "from llm_do import tool_context\n\n"
        "@tool_context\n"
        "async def main(ctx, input: str) -> str:\n"
        "    return await ctx.call_tool('echoer', input)\n"
    )

    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="echoer", instructions="Echo."))

    model = TestModel(call_tools=[], custom_output_text="worker output")

    result = asyncio.run(
        run_tool_async(
            registry=registry,
            tool="main",
            input_data="ping",
            cli_model=model,
        )
    )

    assert result.output == "worker output"


def test_run_tool_async_worker_entrypoint(tmp_path: Path) -> None:
    registry = WorkerRegistry(tmp_path)
    registry.save_definition(WorkerDefinition(name="main", instructions="demo"))

    model = TestModel(call_tools=[], custom_output_text="tool output")

    result = asyncio.run(
        run_tool_async(
            registry=registry,
            tool="main",
            input_data="hello",
            cli_model=model,
        )
    )

    assert result.output == "tool output"


def test_call_tool_extracts_attachments_from_dict_input(tmp_path: Path) -> None:
    """Test that call_tool extracts attachments from dict input when calling workers."""
    # Create a test PDF file
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"%PDF-1.4 test content")

    # Code entry point that calls a worker with dict input containing attachments
    tools_py = tmp_path / "tools.py"
    tools_py.write_text(
        "from llm_do import tool_context\n\n"
        "@tool_context\n"
        "async def main(ctx, input: str) -> str:\n"
        "    return await ctx.call_tool(\n"
        "        'analyzer',\n"
        "        {'input': 'analyze', 'attachments': [input]}\n"
        "    )\n"
    )

    from llm_do import AttachmentPolicy

    registry = WorkerRegistry(tmp_path)
    registry.save_definition(
        WorkerDefinition(
            name="analyzer",
            instructions="Analyze.",
            attachment_policy=AttachmentPolicy(
                max_attachments=1,
                allowed_suffixes=[".pdf"],
            ),
        )
    )

    model = TestModel(call_tools=[], custom_output_text="analysis complete")

    result = asyncio.run(
        run_tool_async(
            registry=registry,
            tool="main",
            input_data=str(test_file),
            cli_model=model,
        )
    )

    assert result.output == "analysis complete"
