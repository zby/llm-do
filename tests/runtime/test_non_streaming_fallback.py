"""Regression tests for non-streaming model behavior with UI callbacks enabled."""

import pytest

from llm_do.runtime import AgentSpec, FunctionEntry, Runtime
from tests.tool_calling_model import ToolCallingModel


@pytest.mark.anyio
async def test_non_streaming_model_runs_with_on_event_at_verbosity_1() -> None:
    """Non-streaming models should still run when only -v style events are needed."""
    events: list[object] = []
    agent_spec = AgentSpec(
        name="non_streaming_agent",
        instructions="Reply briefly.",
        model=ToolCallingModel(tool_calls=[]),
    )

    async def entry_main(input_data, runtime):
        return await runtime.call_agent(agent_spec, input_data)

    runtime = Runtime(on_event=events.append, verbosity=1)
    runtime.register_agents({agent_spec.name: agent_spec})

    result, _ctx = await runtime.run_entry(
        FunctionEntry(name="entry", fn=entry_main),
        {"input": "hello"},
    )

    assert result == "Task completed"
    assert events
