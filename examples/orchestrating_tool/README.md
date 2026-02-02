# Orchestrating Tool Example

This example demonstrates a **tool that orchestrates agents**—a Python tool that internally calls multiple agents to accomplish a complex task.

## The Pattern

The outer LLM sees a single tool:
```
deep_research(question: str) -> str
```

But internally, this tool orchestrates a multi-agent pipeline:
```
deep_research()
    ├── call_agent("query_expander")    # Generate search queries
    ├── call_agent("searcher") × N       # Search in parallel
    └── call_agent("synthesizer")        # Combine findings
```

## Why This Pattern?

**Encapsulation**: The orchestration complexity is hidden from the outer agent. It just calls a tool.

**Deterministic control flow**: The tool decides when to call which agent, using Python's native control flow (loops, conditionals, parallel execution).

**Reusability**: The same orchestrating tool can be used by different entry agents.

**Testability**: The orchestration logic is Python—you can unit test it, mock agents, etc.

## Key Code

In `tools.py`:

```python
@tools.tool
async def deep_research(
    ctx: RunContext[CallContext],
    question: str,
) -> str:
    runtime = ctx.deps  # The CallContext

    # Call agents by name
    queries_json = await runtime.call_agent("query_expander", {"input": question})

    # Parallel execution
    search_tasks = [runtime.call_agent("searcher", {"input": q}) for q in queries]
    findings = await asyncio.gather(*search_tasks)

    # Final synthesis
    answer = await runtime.call_agent("synthesizer", {...})
    return answer
```

## Comparison: Three Orchestration Patterns

| Pattern | Entry | Orchestration | Use when |
|---------|-------|---------------|----------|
| **Agent entry** | LLM | LLM decides tool calls | Orchestration needs reasoning |
| **Code entry** | Python function | Python decides agent calls | Simple deterministic flow |
| **Orchestrating tool** | LLM | Tool contains agent calls | Encapsulated reusable workflows |

The orchestrating tool pattern combines the best of both: the outer LLM can make high-level decisions about *when* to research, while the tool handles *how* to research.

## Running

```bash
llm-do examples/orchestrating_tool/project.json "What are the pros and cons of using Rust vs Go for web services?"
```

Note: This example uses server-side `web_search`, which requires appropriate API access.
