# Undeclared Tool Test

Demonstrates what happens when an LLM tries to call a tool that doesn't exist.

## Run

```bash
uv run examples/undeclared_tool_test/run.py
```

## What It Shows

The script creates an agent with only a `greet` tool, but uses a test model that attempts to call `run_shell`. The output shows the error message returned to the LLM:

```
[hallucinating_agent:1] Tool call: run_shell
  Args: {"command": "ls -la"}

[hallucinating_agent:1] Tool result: run_shell
  Unknown tool name: 'run_shell'. Available tools: 'greet'
```

This error message tells the LLM which tool it tried to call and which tools are actually available, allowing it to recover.

## Why This Matters

When building agents, you may encounter situations where:
- The LLM hallucinates a tool that doesn't exist
- Instructions mention a tool that wasn't added to the toolset
- A tool was removed but instructions weren't updated

This example shows the error handling that helps diagnose these issues.
