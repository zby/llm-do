"""Entry function with filesystem that tries to call shell."""

from llm_do.runtime import entry, WorkerArgs, WorkerRuntime


@entry(
    name="entry_wrong_tool",
    toolsets=["filesystem_project"],  # Has filesystem, not shell
)
async def entry_wrong_tool(args: WorkerArgs, runtime: WorkerRuntime) -> str:
    """Try to call shell tool when only filesystem is declared."""
    prompt = args.prompt_spec().text

    # Try to call run_shell even though we only declared filesystem
    result = await runtime.call("run_shell", {"command": "ls -la"})

    return f"Got result: {result}"
