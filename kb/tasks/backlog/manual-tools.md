# Manual Tools

## Idea

Support tools that can only be invoked by users, not by the LLM - providing a
security boundary against prompt injection.

## Why

Some operations (like `git push`, `deploy`) should never be invokable by the
LLM, even under prompt injection. Manual-only tools are filtered out before
being sent to the LLM, so it literally cannot call them.

**Defense by construction**: The LLM can't invoke what it doesn't know exists.

## Rough Scope

- Add `get_manual_only_tools() -> set[str]` method to toolset pattern
- Filter manual-only tools before passing to `agent.run()`
- Invocation via `/tool <name> [args]` slash command (depends on slash commands)
- Config override to mark tools as manual-only
- TUI display of available manual tools

## Implementation Sketch

```python
class MyToolset(AbstractToolset[WorkerRuntime]):
    async def get_tools(self, ctx) -> dict[str, ToolsetTool]: ...

    def get_manual_only_tools(self) -> set[str]:
        """Return tool names that should not be sent to the LLM."""
        return {"git_push", "deploy"}
```

Runtime filtering:
```python
all_tools = await toolset.get_tools(ctx)
manual_only = toolset.get_manual_only_tools()
llm_tools = {k: v for k, v in all_tools.items() if k not in manual_only}
```

## Why Not Now

Depends on slash commands (task 40) for invocation mechanism.

## Trigger to Activate

Need for security-sensitive tools that humans must invoke explicitly.
