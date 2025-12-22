# Pure Python vs MCP Code Mode

## Core Insight

Both paradigms use **composite tools** - a single tool that orchestrates multiple underlying tools. The key difference is authorship.

## Comparison

| Aspect | MCP Code Mode | llm-do Pure Python |
|--------|---------------|-------------------|
| Composite author | LLM at runtime | Human developer |
| Exposed as | Generic "execute_code" tool | Named domain tool |
| Language | Any (Cloudflare uses TypeScript/V8) | Python |
| Can call back to LLM mid-execution? | No - sandbox completes, then returns | Yes - `ctx.call_tool("worker")` |

## How They Work

**MCP Code Mode**: LLM writes code that calls MCP tools via API bindings. The code IS the tool call - a meta-tool. Insight: LLMs are better at writing code than at synthetic tool-calling format.

**llm-do Pure Python**: Human writes Python that orchestrates tools/workers. Exposed as a single tool. Can interleave deterministic logic with LLM consultations.

## Example Equivalence

```
# MCP Code Mode - LLM generates this at runtime:
const files = await mcp.github.listFiles(repo);
for (const f of files) { ... }

# llm-do - Human writes this, exposed as tool:
@tool_context
async def process_repo(ctx, repo: str):
    files = list_files(repo)           # deterministic
    for f in files:
        analysis = await ctx.call_tool("analyzer", f)  # LLM callback
```

## Key Difference

**Code Mode**: LLM writes **ephemeral** code at runtime for each execution. Solves "LLMs are bad at tool-calling" by letting them write code instead.

**Pure Python**: Humans write **persistent** tools saved in the project repo. Code is reviewed, tested, version-controlled. Solves "I need predictable, auditable orchestration."

Secondary difference: Pure Python tools can call back to LLM workers mid-execution; Code Mode sandboxes run to completion.

## Sources

- [Cloudflare Code Mode](https://blog.cloudflare.com/code-mode/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
