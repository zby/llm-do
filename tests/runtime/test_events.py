"""Tests for event emission in runtime."""
import pytest
from pydantic_ai.messages import FunctionToolCallEvent, FunctionToolResultEvent
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import AgentSpec, FunctionEntry, Runtime, ToolsetSpec
from llm_do.runtime.events import RuntimeEvent, UserMessageEvent
from tests.runtime.helpers import build_runtime_context


class TestContextEventCallback:
    """Tests for CallContext event callback wiring."""

    def test_child_context_inherits_on_event(self):
        events = []

        def callback(e):
            events.append(e)

        ctx = build_runtime_context(
            model="test",
            on_event=callback,
        )
        child = ctx.spawn_child(
            active_toolsets=ctx.frame.config.active_toolsets,
            model=ctx.frame.config.model,
            invocation_name=ctx.frame.config.invocation_name,
        )
        assert child.config.on_event is callback

    def test_child_context_inherits_verbosity(self):
        ctx = build_runtime_context(
            model="test",
            verbosity=2,
        )
        child = ctx.spawn_child(
            active_toolsets=ctx.frame.config.active_toolsets,
            model=ctx.frame.config.model,
            invocation_name=ctx.frame.config.invocation_name,
        )
        assert child.config.verbosity == 2


@pytest.mark.anyio
async def test_entry_emits_user_message_event() -> None:
    events: list[RuntimeEvent] = []

    async def main(input_data, _runtime):
        from llm_do.runtime.args import get_display_text

        return get_display_text(input_data.prompt_messages())

    entry = FunctionEntry(name="entry", fn=main)

    runtime = Runtime(on_event=events.append)
    result, _ctx = await runtime.run_entry(entry, {"input": "hello"})

    assert result == "hello"
    user_events = [e for e in events if isinstance(e.event, UserMessageEvent)]
    assert user_events
    assert user_events[0].event.content == "hello"


@pytest.mark.anyio
async def test_agent_emits_tool_events() -> None:
    events: list[RuntimeEvent] = []

    def build_toolset():
        toolset = FunctionToolset()

        @toolset.tool
        def add(a: int, b: int) -> int:
            return a + b

        return toolset

    agent_spec = AgentSpec(
        name="calculator",
        instructions="Use add tool.",
        model=TestModel(call_tools=["add"], custom_output_text="done"),
        toolset_specs=[ToolsetSpec(factory=build_toolset)],
    )

    async def entry_main(input_data, runtime):
        return await runtime.call_agent(agent_spec, input_data)

    entry = FunctionEntry(name="entry", fn=entry_main)

    runtime = Runtime(on_event=events.append)
    runtime.register_agents({agent_spec.name: agent_spec})
    await runtime.run_entry(entry, {"input": "go"})

    tool_calls = [e for e in events if isinstance(e.event, FunctionToolCallEvent)]
    tool_results = [e for e in events if isinstance(e.event, FunctionToolResultEvent)]

    assert tool_calls
    assert tool_results
    assert tool_calls[0].event.part.tool_name == "add"
    assert tool_results[0].event.result.tool_name == "add"
