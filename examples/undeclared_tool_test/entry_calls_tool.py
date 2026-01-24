"""Entry toolset that runs an agent which tries to call an undeclared tool."""

from llm_do.runtime import AgentSpec, EntrySpec

MODEL = "anthropic:claude-haiku-4-5"

UNDECLARED_AGENT = AgentSpec(
    name="undeclared_tool_agent",
    instructions=(
        "You must use the read_file tool to inspect the current directory. "
        "Call read_file(path='.') and summarize the result."
    ),
    model=MODEL,
)


async def main(input_data, runtime) -> str:
    """Invoke the agent that will attempt to call a missing tool."""
    return await runtime.call_agent(UNDECLARED_AGENT, input_data)


ENTRY_SPEC = EntrySpec(name="entry_calls_tool", main=main)
