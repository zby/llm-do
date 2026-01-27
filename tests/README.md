# Testing Patterns in llm-do

This guide documents the testing strategies and patterns used in llm-do. The codebase uses PydanticAI's dependency injection system to enable comprehensive testing without API calls.

## Quick Reference

| Pattern | Use Case | Example |
|---------|----------|---------|
| **TestModel** | End-to-end agent flow without API calls | `AgentSpec(...)` + `FunctionEntry(...)` + `Runtime.run_entry(...)` |
| **ToolCallingModel** | Deterministic tool-call sequences | `ToolCallingModel(tool_calls=...)` + toolset assertions |
| **Real model (integration)** | Verify critical end-to-end flows | `tests/live/` (marked) |

## Using PydanticAI's TestModel

### When to Use

Use `TestModel` when you need to test the **full agent behavior** including:
- Agent definitions load correctly
- Tools are registered and callable
- Structured output schemas validate
- Tool calling behavior works end-to-end

### How It Works

`TestModel` is a fake LLM from PydanticAI that:
- Returns deterministic outputs without API calls
- Exercises the full agent execution flow
- Can be configured to return specific text or pseudo-random responses

### Example

```python
from pydantic_ai.models.test import TestModel

from llm_do.runtime import AgentSpec, FunctionEntry, Runtime


async def main(input_data, runtime):
    return await runtime.call_agent("my_agent", input_data)


async def test_agent_executes_with_tools(test_model: TestModel):
    agent = AgentSpec(name="my_agent", instructions="Process this", model=test_model)
    entry = FunctionEntry(name="main", main=main)

    runtime = Runtime()
    runtime.register_agents({"my_agent": agent})

    result, _ctx = await runtime.run_entry(entry, "process this")
    assert result is not None
```

## Using ToolCallingModel

### When to Use

Use `ToolCallingModel` when you need **deterministic tool-call sequences** and want to
assert tool wiring or approval behavior without relying on LLM reasoning.

### Example

```python
from llm_do.runtime import AgentSpec, FunctionEntry, Runtime, ToolsetSpec
from tests.tool_calling_model import ToolCallingModel


def build_tools(_ctx):
    tools = FunctionToolset()

    @tools.tool
    def add(a: int, b: int) -> int:
        return a + b

    return tools


async def main(input_data, runtime):
    return await runtime.call_agent("calc", input_data)


async def test_tool_call_flow():
    model = ToolCallingModel(tool_calls=[{"name": "add", "args": {"a": 1, "b": 2}}])
    agent = AgentSpec(name="calc", instructions="Use tools", model=model, toolset_specs=[ToolsetSpec(factory=build_tools)])
    entry = FunctionEntry(name="main", main=main)

    runtime = Runtime()
    runtime.register_agents({"calc": agent})

    result, _ctx = await runtime.run_entry(entry, "go")
    assert result is not None
```

## When to Use Each Pattern

- **TestModel**: default for unit tests that exercise agent/tool integration.
- **ToolCallingModel**: when you need deterministic tool-call sequences.
- **Real models**: only for minimal live integration tests.

## Common Pitfalls

❌ **Don't use real models in unit tests**
```python
# BAD: slow, costs money, non-deterministic
result = await runtime.run_entry(entry, "...")
```

✅ **Use TestModel or ToolCallingModel**
```python
# GOOD: fast, deterministic
agent = AgentSpec(name="my_agent", instructions="...", model=TestModel())
```

## Further Reading

- PydanticAI TestModel docs: https://ai.pydantic.dev/testing/
- Pytest fixtures: https://docs.pytest.org/en/stable/fixture.html
