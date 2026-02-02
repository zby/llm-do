---
description: LLM-authored tools that can only call agents, enabling safe dynamic orchestration
---

# Pure Dynamic Tools

Design for LLM-authored tools that execute safely because they can only call agents.

## Motivation

The `orchestrating_tool` example shows the value of code-level orchestration:
- Parallel execution (`asyncio.gather`)
- Control flow (loops, conditionals)
- Data transformation (JSON parsing, string manipulation)

Currently this code is human-authored. The goal: **let the LLM write orchestration tools at runtime**.

### RLM Insight

From the [RLM comparison](related_works/recursive-llm-comparison.md):

> "recursive-llm has no approvals because it exposes no side-effectful tools"

RLM achieves safety by having only one primitive: `recursive_llm(sub_query, sub_context)`. All computation happens through LLM → LLM recursion with no external effects.

We can apply the same pattern: LLM-authored code that can only call `call_agent`.

## Design

### The Pure Tool Pattern

```python
# LLM creates a tool dynamically
tool_create(
    name="deep_research",
    description="Research using multiple agents in parallel",
    parameters={"question": "str"},
    code="""
async def run(question, call_agent):
    # Step 1: Expand query
    queries = json.loads(await call_agent("query_expander", {"input": question}))

    # Step 2: Search in parallel
    findings = await asyncio.gather(*[
        call_agent("searcher", {"input": q}) for q in queries
    ])

    # Step 3: Synthesize
    return await call_agent("synthesizer", {"input": findings})
"""
)

# Then another agent (or the same one) can call it
result = tool_call("deep_research", {"question": "..."})
```

### Execution Sandbox

Building on the `rlm_repl` example's RestrictedPython approach:

1. **RestrictedPython** — compile and execute in sandbox
2. **Inject only `call_agent`** — the single capability for effects
3. **Allow computation** — json, asyncio, loops, math, string ops
4. **No I/O** — no file, network, subprocess access

### Why This Is Safe

Since the only capability is `call_agent`:
- All side effects happen through agents
- Agents have their own approval policies
- The tool itself needs no approval (it's pure computation + delegation)
- LLM can safely write orchestration logic

### Comparison with Existing Patterns

| Pattern | Code Author | Capabilities | Safety Model |
|---------|-------------|--------------|--------------|
| Static tools (`tools.py`) | Human | Full Python | Trust author |
| `dynamic_agents` | LLM | None (just prompts) | No code execution |
| `rlm_repl` | LLM | RestrictedPython + context | Sandbox |
| **Pure tools** | LLM | RestrictedPython + `call_agent` | Sandbox + delegation |

## Implementation Sketch

### New Toolset

```python
class PureToolsToolset(AbstractToolset):
    """Toolset for LLM-authored pure tools."""

    # Tools exposed to LLM:
    # - tool_create(name, description, parameters, code)
    # - tool_call(name, args)
    # - tool_list()
```

### Executor

```python
class PureToolExecutor:
    """Execute LLM-authored code with only call_agent available."""

    def __init__(self, call_agent_fn):
        self.call_agent = call_agent_fn

    async def execute(self, code: str, args: dict) -> Any:
        # 1. RestrictedPython compile
        byte_code = compile_restricted_exec(code)

        # 2. Build restricted globals
        restricted_globals = {
            # Computation
            "json": json,
            "asyncio": asyncio_subset,  # Only gather, sleep
            "math": math,
            # ... basic builtins from rlm_repl

            # The only capability
            "call_agent": self.call_agent,
        }

        # 3. Execute
        env = {"args": args}
        exec(byte_code.code, restricted_globals, env)
        return await env["run"](**args, call_agent=self.call_agent)
```

### Storage

Pure tools could be stored similarly to dynamic agents:
- Session-only dict: `ctx.dynamic_tools[name] = PureToolSpec(...)`
- Optional persistence to `generated_tools_dir`

## Open Questions

1. **Sync vs async** — Should pure tools be async-only (to support `asyncio.gather`)? Or support both?

2. **Parameter schema** — How does the LLM specify the tool's input schema?
   - JSON Schema dict?
   - Simple type hints in `parameters={"question": "str"}`?
   - Inferred from the `run` function signature?

3. **Persistence** — Should created tools persist (like dynamic agents write `.agent` files) or be session-only?

4. **Naming** — `pure_tools`, `dynamic_tools`, `llm_tools`, `sandbox_tools`?

5. **Error handling** — How to surface RestrictedPython compilation errors or runtime errors to the LLM?

6. **Recursion** — Can a pure tool call another pure tool? (Probably yes, via `tool_call` being available)

7. **Approval for tool_create** — Should creating a pure tool require approval? The tool itself is safe, but reviewing the code might be valuable for debugging/auditing.

## Related

- `examples/orchestrating_tool/` — human-authored version of this pattern
- `examples/rlm_repl/` — RestrictedPython sandbox foundation
- `llm_do/toolsets/dynamic_agents.py` — similar pattern for agents
- `docs/notes/related_works/recursive-llm-comparison.md` — RLM analysis
