"""Entry toolset with filesystem that tries to call shell."""

from pathlib import Path

from llm_do.runtime import AgentSpec, EntrySpec
from llm_do.toolsets.builtins import build_builtin_toolsets

PROJECT_ROOT = Path(__file__).parent.resolve()
MODEL = "anthropic:claude-haiku-4-5"

BUILTINS = build_builtin_toolsets(Path.cwd(), PROJECT_ROOT)
FILESYSTEM_TOOLSET = BUILTINS["filesystem_project"]

WRONG_TOOL_AGENT = AgentSpec(
    name="wrong_tool_agent",
    instructions=(
        "You must use the run_shell tool to list files. "
        "Call run_shell(command='ls -la') and summarize the result."
    ),
    model=MODEL,
    toolset_specs=[FILESYSTEM_TOOLSET],
)


async def main(input_data, runtime) -> str:
    """Invoke the agent that will attempt to call an undeclared tool."""
    return await runtime.call_agent(WRONG_TOOL_AGENT, input_data)


ENTRY_SPEC = EntrySpec(name="entry_wrong_tool", main=main)
