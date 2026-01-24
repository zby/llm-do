import pytest
from pydantic_ai.models.test import TestModel

from llm_do.runtime import AgentEntry, PromptContent, ToolsetBuildContext, WorkerArgs
from llm_do.runtime.args import normalize_input
from tests.runtime.helpers import build_call_scope


class TopicInput(WorkerArgs):
    topic: str
    limit: int = 3

    def prompt_messages(self) -> list[PromptContent]:
        return [f"topic={self.topic}\nlimit={self.limit}"]


class TextInput(WorkerArgs):
    input: str

    def prompt_messages(self) -> list[PromptContent]:
        return [self.input]


@pytest.mark.anyio
async def test_entry_tool_schema_uses_schema_in() -> None:
    entry_instance = AgentEntry(
        name="topic_entry",
        instructions="Extract topic details.",
        schema_in=TopicInput,
        model=TestModel(),
    )
    scope = build_call_scope(toolsets=[], model="test")
    run_ctx = scope._make_run_context(entry_instance.name)

    toolset = entry_instance.as_toolset_spec().factory(
        ToolsetBuildContext(worker_name=entry_instance.name)
    )
    tools = await toolset.get_tools(run_ctx)
    tool_def = tools[entry_instance.name].tool_def
    schema = tool_def.parameters_json_schema
    properties = schema.get("properties", {})

    assert "topic" in properties
    assert "input" not in properties


@pytest.mark.anyio
async def test_entry_tool_description_prefers_description() -> None:
    entry_instance = AgentEntry(
        name="desc_entry",
        instructions="Instructions fallback.",
        description="Short tool summary.",
        model=TestModel(),
    )
    scope = build_call_scope(toolsets=[], model="test")
    run_ctx = scope._make_run_context(entry_instance.name)

    toolset = entry_instance.as_toolset_spec().factory(
        ToolsetBuildContext(worker_name=entry_instance.name)
    )
    tools = await toolset.get_tools(run_ctx)
    tool_def = tools[entry_instance.name].tool_def

    assert tool_def.description == "Short tool summary."


@pytest.mark.anyio
async def test_normalize_input_accepts_string() -> None:
    """Simple strings are accepted directly without a schema."""
    args, messages = normalize_input(None, "hello")
    assert args is None
    assert messages == ["hello"]


@pytest.mark.anyio
async def test_normalize_input_accepts_dict_with_schema() -> None:
    """Dict input with a schema returns structured args."""
    args, messages = normalize_input(TextInput, {"input": "hello"})
    assert isinstance(args, TextInput)
    assert messages == ["hello"]
