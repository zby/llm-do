# Manual Tools

## Prerequisites
- [ ] 40-slash-commands (need `/tool` command for invocation)

## Goal
Support tools that can only be invoked by users, not by the LLM - providing a security boundary against prompt injection.

## Background

Some operations (like `git push`, `deploy`) should never be invokable by the LLM, even under prompt injection. Manual-only tools are filtered out before being sent to the LLM, so it literally cannot call them.

See `docs/notes/golem-forge-manual-tools.md` for detailed design analysis.

## Key Concept

**Defense by construction**: Manual-only tools are never passed to the LLM. The LLM can't invoke what it doesn't know exists.

## Tasks

### Phase 1: Toolset Interface
- [ ] Add `get_manual_only_tools() -> set[str]` method to `AbstractToolset` pattern
- [ ] Default implementation returns empty set (all tools available to LLM)
- [ ] Update toolset documentation

### Phase 2: Runtime Filtering
- [ ] Filter manual-only tools before passing to `agent.run()`
- [ ] Keep manual tools available for CLI/TUI invocation
- [ ] Add logging when tools are filtered

### Phase 3: Invocation via Slash Command
- [ ] Register `/tool <name> [args]` command (via Task 40 registry)
- [ ] Parse tool arguments (JSON or key=value format)
- [ ] Execute tool through normal toolset `call_tool()` path
- [ ] Display result in TUI

### Phase 4: Config Override
- [ ] Allow config to override default execution mode:
  ```yaml
  toolsets:
    custom:
      dangerous_function:
        mode: manual  # Override to manual-only
  ```
- [ ] Toolsets read config and adjust `get_manual_only_tools()` accordingly

### Phase 5: TUI Integration
- [ ] Show available manual tools (command or UI element)
- [ ] Consider: category/label metadata for grouping

## Current State
Not started. Design documented in notes.

## Implementation Approach

Since `AbstractToolset` comes from pydantic-ai, avoid upstream changes:

```python
class MyToolset(AbstractToolset[WorkerContext]):
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

## Notes
- This is a security feature, not just UX
- Future: propose `execution_mode` upstream to pydantic-ai if pattern proves valuable
- Headless mode: error if workflow needs manual tool (or `--allow-manual <tool>` for explicit opt-in)

## References
- Design analysis: `docs/notes/golem-forge-manual-tools.md`
- Comparison: `docs/notes/toolset-comparison-golem-forge.md`
- golem-forge implementation: `/home/zby/llm/golem-forge`
