import pytest
from pydantic import BaseModel

from llm_do.ctx_runtime import Worker, WorkerRuntime


class TopicInput(BaseModel):
    topic: str
    limit: int = 3


class TextInput(BaseModel):
    input: str


@pytest.mark.anyio
async def test_worker_tool_schema_uses_schema_in() -> None:
    worker = Worker(
        name="topic_worker",
        instructions="Extract topic details.",
        schema_in=TopicInput,
    )
    ctx = WorkerRuntime(toolsets=[], model="test-model")
    run_ctx = ctx._make_run_context(worker.name, "test-model", ctx)

    tools = await worker.get_tools(run_ctx)
    tool_def = tools[worker.name].tool_def
    schema = tool_def.parameters_json_schema
    properties = schema.get("properties", {})

    assert "topic" in properties
    assert "input" not in properties


@pytest.mark.anyio
async def test_ctx_call_wraps_plain_text_for_input_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    worker = Worker(
        name="text_worker",
        instructions="Echo input.",
        schema_in=TextInput,
    )
    captured: dict[str, object] = {}

    async def fake_call(self, input_data, ctx, run_ctx):
        captured["data"] = input_data
        return input_data

    monkeypatch.setattr(worker, "call", fake_call.__get__(worker, Worker))
    ctx = WorkerRuntime(toolsets=[worker], model="test-model")

    await ctx.call("text_worker", "hello")

    assert captured["data"] == {"input": "hello"}


@pytest.mark.anyio
async def test_ctx_call_passes_plain_text_for_non_input_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    worker = Worker(
        name="topic_worker",
        instructions="Process topic.",
        schema_in=TopicInput,
    )
    captured: dict[str, object] = {}

    async def fake_call(self, input_data, ctx, run_ctx):
        captured["data"] = input_data
        return input_data

    monkeypatch.setattr(worker, "call", fake_call.__get__(worker, Worker))
    ctx = WorkerRuntime(toolsets=[worker], model="test-model")

    await ctx.call("topic_worker", "hello")

    assert captured["data"] == "hello"
