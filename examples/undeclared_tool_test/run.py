#!/usr/bin/env python
"""Demonstrates error messages when an LLM tries to call undeclared tools.

This uses a test model with a canned response that attempts to call a
non-existent tool, showing what error message the LLM receives.

Run with:
    uv run examples/undeclared_tool_test/run.py
"""

import asyncio

# Import test utilities
import sys
from pathlib import Path

from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import AgentSpec, CallContext, FunctionEntry
from llm_do.ui import run_ui

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tests"))
from conftest_models import ToolCall  # noqa: E402

PROJECT_ROOT = Path(__file__).parent.resolve()


def build_simple_toolset(_ctx):
    """Build a toolset with just one tool."""
    toolset = FunctionToolset()

    @toolset.tool
    def greet(name: str) -> str:
        """Greet someone by name."""
        return f"Hello, {name}!"

    return toolset


# Create a test model that tries to call a non-existent tool, then gives up
def create_hallucinating_model():
    """Model that calls a non-existent tool, then reports the error."""
    from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    call_count = 0

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal call_count
        call_count += 1

        # First call: try to use non-existent tool
        if call_count == 1:
            return ModelResponse(parts=[
                ToolCall("run_shell", {"command": "ls -la"}).to_part()
            ])

        # After getting error, acknowledge it
        return ModelResponse(parts=[
            TextPart(content="I tried to call run_shell but it's not available.")
        ])

    async def stream_respond(messages, info):
        response = respond(messages, info)
        for part in response.parts:
            if hasattr(part, 'content'):
                yield part.content
            else:
                # Tool call - yield as delta
                from pydantic_ai.models.function import DeltaToolCall
                yield {0: DeltaToolCall(
                    name=part.tool_name,
                    json_args=part.args,
                    tool_call_id=part.tool_call_id,
                )}

    return FunctionModel(respond, stream_function=stream_respond)


AGENT = AgentSpec(
    name="hallucinating_agent",
    model=create_hallucinating_model(),
    instructions="You are a helpful assistant.",
    toolsets=[build_simple_toolset],  # Only has 'greet' tool
)


async def main(_input_data, runtime: CallContext) -> str:
    """Run the agent that will try to call a non-existent tool."""
    return await runtime.call_agent(AGENT, {"input": "List files in the current directory"})


ENTRY = FunctionEntry(name="main", fn=main)


def cli_main():
    """Run the example."""
    print("Demonstrating error when LLM calls undeclared tool")
    print("=" * 60)
    print("The agent has only the 'greet' tool available.")
    print("The test model will try to call 'run_shell' which doesn't exist.")
    print("=" * 60)
    print()

    outcome = asyncio.run(run_ui(
        entry=ENTRY,
        input={"input": ""},
        project_root=PROJECT_ROOT,
        approval_mode="approve_all",
        mode="headless",
        verbosity=2,
    ))

    print()
    print("=" * 60)
    if outcome.result:
        print("Result:", outcome.result)
    else:
        print("Agent completed (see tool result above for error message)")


if __name__ == "__main__":
    cli_main()
