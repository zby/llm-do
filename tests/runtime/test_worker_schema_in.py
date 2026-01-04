import pytest
from pydantic import BaseModel

from llm_do.runtime import Worker, WorkerRuntime


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
async def test_worker_call_coerces_plain_text_for_input_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """Worker.call() coerces plain text to {"input": text} when schema_in has an 'input' field."""
    from llm_do.runtime.input_utils import coerce_worker_input

    # Verify coercion logic directly
    result = coerce_worker_input(TextInput, "hello")
    assert result == {"input": "hello"}


@pytest.mark.anyio
async def test_worker_call_passes_plain_text_for_non_input_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """Worker.call() passes plain text through when schema_in lacks an 'input' field."""
    from llm_do.runtime.input_utils import coerce_worker_input

    # Verify coercion logic directly - TopicInput has 'topic', not 'input'
    result = coerce_worker_input(TopicInput, "hello")
    assert result == "hello"
