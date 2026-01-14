import pytest

from llm_do.runtime import PromptSpec, ToolsetBuildContext, Worker, WorkerArgs
from llm_do.runtime.args import ensure_worker_args
from tests.runtime.helpers import build_runtime_context


class TopicInput(WorkerArgs):
    topic: str
    limit: int = 3

    def prompt_spec(self) -> PromptSpec:
        return PromptSpec(text=f"topic={self.topic}\nlimit={self.limit}")


class TextInput(WorkerArgs):
    input: str

    def prompt_spec(self) -> PromptSpec:
        return PromptSpec(text=self.input)


@pytest.mark.anyio
async def test_worker_tool_schema_uses_schema_in() -> None:
    worker = Worker(
        name="topic_worker",
        instructions="Extract topic details.",
        schema_in=TopicInput,
    )
    ctx = build_runtime_context(toolsets=[], model="test")
    run_ctx = ctx._make_run_context(worker.name, "test", ctx)

    toolset = worker.as_toolset_spec().factory(
        ToolsetBuildContext(worker_name=worker.name)
    )
    tools = await toolset.get_tools(run_ctx)
    tool_def = tools[worker.name].tool_def
    schema = tool_def.parameters_json_schema
    properties = schema.get("properties", {})

    assert "topic" in properties
    assert "input" not in properties


@pytest.mark.anyio
async def test_worker_tool_description_prefers_description() -> None:
    worker = Worker(
        name="desc_worker",
        instructions="Instructions fallback.",
        description="Short tool summary.",
    )
    ctx = build_runtime_context(toolsets=[], model="test")
    run_ctx = ctx._make_run_context(worker.name, "test", ctx)

    toolset = worker.as_toolset_spec().factory(
        ToolsetBuildContext(worker_name=worker.name)
    )
    tools = await toolset.get_tools(run_ctx)
    tool_def = tools[worker.name].tool_def

    assert tool_def.description == "Short tool summary."


@pytest.mark.anyio
async def test_worker_args_validation_requires_dict() -> None:
    """Worker args require a structured payload."""
    with pytest.raises(TypeError, match="Worker inputs must be dict"):
        ensure_worker_args(TextInput, "hello")


@pytest.mark.anyio
async def test_worker_args_validation_accepts_dict() -> None:
    """Worker args validation returns the expected WorkerArgs instance."""
    result = ensure_worker_args(TextInput, {"input": "hello"})
    assert isinstance(result, TextInput)
