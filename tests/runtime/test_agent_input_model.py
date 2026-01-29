import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import RunUsage

from llm_do.runtime import AgentArgs, AgentSpec, PromptContent, PromptInput
from llm_do.runtime.args import normalize_input
from llm_do.toolsets.agent import agent_as_toolset
from tests.runtime.helpers import build_runtime_context


class TopicInput(AgentArgs):
    topic: str
    limit: int = 3

    def prompt_messages(self) -> list[PromptContent]:
        return [f"topic={self.topic}\nlimit={self.limit}"]


class TextInput(AgentArgs):
    input: str

    def prompt_messages(self) -> list[PromptContent]:
        return [self.input]


class OtherInput(AgentArgs):
    input: str

    def prompt_messages(self) -> list[PromptContent]:
        return [self.input]


@pytest.mark.anyio
async def test_agent_tool_schema_uses_input_model() -> None:
    spec = AgentSpec(
        name="topic_agent",
        instructions="Extract topic details.",
        model=TestModel(),
        input_model=TopicInput,
    )
    ctx = build_runtime_context(toolsets=[], model="test")
    run_ctx = RunContext(
        deps=ctx,
        model=TestModel(),
        usage=RunUsage(),
        prompt="test",
        messages=[],
        run_step=0,
        retry=0,
        tool_name="main",
    )

    toolset = agent_as_toolset(spec).factory()
    tools = await toolset.get_tools(run_ctx)
    tool_def = tools[spec.name].tool_def
    schema = tool_def.parameters_json_schema
    properties = schema.get("properties", {})

    assert "topic" in properties
    assert "input" not in properties


@pytest.mark.anyio
async def test_agent_tool_description_prefers_description() -> None:
    spec = AgentSpec(
        name="desc_agent",
        instructions="Instructions fallback.",
        description="Short tool summary.",
        model=TestModel(),
    )
    ctx = build_runtime_context(toolsets=[], model="test")
    run_ctx = RunContext(
        deps=ctx,
        model=TestModel(),
        usage=RunUsage(),
        prompt="test",
        messages=[],
        run_step=0,
        retry=0,
        tool_name="main",
    )

    toolset = agent_as_toolset(spec).factory()
    tools = await toolset.get_tools(run_ctx)
    tool_def = tools[spec.name].tool_def

    assert tool_def.description == "Short tool summary."


@pytest.mark.anyio
async def test_normalize_input_rejects_string() -> None:
    """Raw strings are rejected; inputs must be dict or AgentArgs."""
    with pytest.raises(TypeError, match="dict or AgentArgs"):
        normalize_input(None, "hello")


@pytest.mark.anyio
async def test_normalize_input_rejects_list() -> None:
    """Raw message lists are rejected; inputs must be dict or AgentArgs."""
    with pytest.raises(TypeError, match="dict or AgentArgs"):
        normalize_input(None, ["hello"])


@pytest.mark.anyio
async def test_normalize_input_accepts_dict_with_input_model() -> None:
    """Dict input with an input model returns structured args."""
    args, messages = normalize_input(TextInput, {"input": "hello"})
    assert isinstance(args, TextInput)
    assert messages == ["hello"]


@pytest.mark.anyio
async def test_normalize_input_defaults_to_prompt_input() -> None:
    args, messages = normalize_input(None, {"input": "hello"})
    assert isinstance(args, PromptInput)
    assert messages == ["hello"]


@pytest.mark.anyio
async def test_normalize_input_rejects_wrong_agent_args() -> None:
    args = OtherInput(input="hello")
    with pytest.raises(TypeError, match="Expected TextInput"):
        normalize_input(TextInput, args)
