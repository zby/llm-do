"""Entry function with filesystem that tries to call shell."""

from llm_do.runtime import WorkerArgs, entry


@entry(
    name="entry_wrong_tool",
    toolsets=["filesystem_project"],  # Has filesystem, not shell
)
async def entry_wrong_tool(args: WorkerArgs, scope) -> str:
    """Try to call shell tool when only filesystem is declared."""
    # Try to call run_shell even though we only declared filesystem
    result = await scope.call_tool("run_shell", {"command": "ls -la"})

    return f"Got result: {result}"
