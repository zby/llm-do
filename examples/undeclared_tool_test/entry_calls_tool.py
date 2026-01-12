"""Entry function that tries to call a tool it didn't declare."""

from llm_do.runtime import WorkerArgs, WorkerRuntime, entry


@entry(
    name="entry_calls_tool",
    toolsets=[],  # No toolsets declared!
)
async def entry_calls_tool(args: WorkerArgs, runtime: WorkerRuntime) -> str:
    """Try to call a tool without declaring it."""
    # Try to call read_file even though we didn't declare filesystem toolset
    result = await runtime.call("read_file", {"path": "."})

    return f"Got result: {result}"
