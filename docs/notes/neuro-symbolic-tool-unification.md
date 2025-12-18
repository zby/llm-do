# Neuro-Symbolic Tool Unification

## Core Insight

Workers and tools are the same thing. A worker is just a tool whose implementation is an LLM agent loop. This unification enables **dual recursion**:

- **LLM → Tool**: Standard agent loop (LLM calls tools)
- **Tool → LLM**: Tools can make nested LLM calls for decisions

This creates a true neuro-symbolic system where neural (LLM) and symbolic (deterministic code) components interleave recursively.

Note: Tool → LLM is a **nested call**, not a callback. We're going deeper into the call stack, not returning up. The context (cost tracking, approvals, depth) flows down through the entire tree.

## The Spectrum

```
Pure Tool ←————————————————————→ Agent Tool (Worker)
(all symbolic)                   (all neural)

read_file ──── smart_refactor ──── code_reviewer
   │                 │                   │
   │           hybrid: mostly           │
   │           deterministic,      full LLM agent
   │           calls LLM when stuck     loop
   │                                    │
no LLM ◄─────────────────────────► only LLM
```

## Dual Recursion

```
┌──────────────────────────────────────────┐
│                                          │
│   LLM ──calls──▶ Tool ──calls──▶ LLM     │
│    │               │               │     │
│    ▼               ▼               ▼     │
│  reason         execute          reason  │
│  decide         compute          decide  │
│  generate       validate         assist  │
│                                          │
└──────────────────────────────────────────┘

Neural ←→ Symbolic ←→ Neural ←→ Symbolic ...
```

## Properties

| Aspect | Neural (LLM) | Symbolic (Tool) |
|--------|--------------|-----------------|
| Reasoning | Fuzzy, contextual | Deterministic, precise |
| Errors | Graceful degradation | Fail fast, typed |
| Cost | Expensive | Cheap |
| Auditability | Hard | Easy |
| Flexibility | High | Low |

## Sync vs Async Tools

**Not all tools need to be async.** Only tools that make nested LLM calls require async.

```
Pure Tool (sync)     Hybrid Tool (async)     Agent Tool (async)
      │                     │                       │
      ▼                     ▼                       ▼
  def foo()          async def bar()         async def baz()
      │                     │                       │
   no ctx               needs ctx               needs ctx
   no await            await llm_ask          await llm_agent
```

**The framework detects and handles both:**

```python
def call_tool(tool_fn, args, ctx):
    if inspect.iscoroutinefunction(tool_fn):
        return await tool_fn(**args, ctx=ctx)
    else:
        return tool_fn(**args)  # sync tools don't need ctx
```

**Benefits:**
- Simple tools stay simple (no `async def`, no `await`, no `ctx`)
- Only tools that need LLM access take `ToolContext`
- Lower barrier for tool authors
- Framework handles the bridging

### Why Async for LLM Calls?

A natural question: if tool execution is sequential (we always wait for each tool to complete), why use async at all for LLM-calling tools?

```
Tool execution is logically blocking:
  LLM → tool → nested LLM → tool → ...
              ↓
         we wait at each step anyway
```

**The async is not for parallelism in tool execution.** It's for the UI plane:

```
┌─────────────────────────────────────────┐
│  UI Plane (must stay responsive)        │
│  - Stream LLM tokens as they arrive     │
│  - Update display during long ops       │
│  - Handle Ctrl+C interrupts             │
│  - Show progress indicators             │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  Tool Plane (sequential execution)      │
│  - Tools run one at a time              │
│  - Each completes before next starts    │
│  - Logically synchronous                │
└─────────────────────────────────────────┘
```

Async lets us yield control to the event loop so the UI can update while waiting for LLM responses. Without it, the UI would freeze during LLM calls.

**Alternative considered:** Run sync tools in thread pool (`asyncio.to_thread`). Rejected because nested LLM calls from within a thread become awkward - you're in a sync context needing to call async LLM APIs.

## Tool Context API

Tools that need nested LLM calls receive a context. **Pure tools don't need it.**

```python
class ToolContext:
    # Shared state (flows through entire call tree)
    cost_tracker: CostTracker        # Accumulates costs across all nested calls
    approval_controller: ApprovalController  # Handles approvals at any depth
    depth: int                       # Current nesting depth (for limits)

    # Nested LLM call - quick question
    async def llm_ask(self, prompt: str) -> str: ...

    # Nested LLM call - full agent loop (what agent tools use)
    async def llm_agent(
        self,
        system: str,
        tools: list[Tool],
        input: Any
    ) -> Any: ...

    # Call another tool (uniform interface)
    async def call_tool(self, name: str, args: dict) -> Any: ...
```

The context is passed down through the entire call tree:
```
LLM call (depth=0, cost=0)
  └─▶ tool call
        └─▶ nested LLM call (depth=1, cost+=N)
              └─▶ tool call
                    └─▶ nested LLM call (depth=2, cost+=M)
```

Cost and approvals are tracked globally, not per-call.

## Examples

### Pure Tool (sync, no context)

```python
# Simple - no async, no context needed
def read_file(path: str) -> str:
    return Path(path).read_text()

def list_directory(path: str) -> list[str]:
    return os.listdir(path)

def run_grep(pattern: str, path: str) -> str:
    result = subprocess.run(["grep", "-r", pattern, path], capture_output=True)
    return result.stdout.decode()
```

### Hybrid Tool (async, needs context)

```python
async def smart_refactor(file: str, ctx: ToolContext) -> str:
    # Sync operations are fine
    code = Path(file).read_text()
    issues = run_linter(code)

    if issues.ambiguous:
        # Only this part needs async - nested LLM call
        decision = await ctx.llm_ask(
            f"Found ambiguous issues: {issues}. How to proceed?"
        )
        issues = apply_decision(issues, decision)

    return apply_fixes(code, issues)
```

### Agent Tool (async, needs context)

```python
async def code_reviewer(input: str, ctx: ToolContext) -> str:
    return await ctx.llm_agent(
        system="You are a senior code reviewer...",
        tools=[read_file, grep, glob],  # Can use sync tools
        input=input
    )
```

## Tool Definition Format

```yaml
# Pure tool - references Python function
name: read_file
type: function
function: llm_do.tools.filesystem:read_file

---

# Agent tool (worker) - inline LLM agent
name: code-reviewer
type: agent
model: claude-sonnet-4
tools: [read_file, grep, glob]
---
You are a senior code reviewer...
```

The `type` field signals implementation:
- `function`: Call Python function
- `agent`: Run LLM agent loop with this prompt

## Progressive Hardening

The unified model enables natural evolution:

```
v1: Agent tool (all neural)
    Everything done by LLM reasoning

v2: Hybrid (extract patterns)
    Deterministic parts crystallize into code
    LLM handles edge cases

v3: Pure tool (all symbolic)
    LLM fully replaced by deterministic logic
    Only used when patterns are stable
```

This is the "neural → symbolic" compilation path. The system learns which parts need flexibility and which can be hardened.

## What Changes

### Removed
- `DelegationToolset` as separate concept
- `worker_call` as special tool
- Worker vs Tool distinction
- `SandboxConfig` (container handles isolation)

### Unified
- Tools and workers share same interface
- Tools can be sync or async (framework detects)
- Only tools needing LLM access receive `ToolContext`
- Tool calling tool = function calling function

### Added
- `ToolContext.llm_ask()` - quick nested LLM call
- `ToolContext.llm_agent()` - full agent loop
- `type: agent` in tool definitions

## High-Level Implementation Plan

### Phase 1: Tool Context with Nested LLM Calls
- Add `ToolContext` with `llm_ask()` and `llm_agent()` methods
- Context carries cost tracker, approval controller, depth
- Pass context to all tool calls
- Existing tools ignore it (backwards compatible)

### Phase 2: Unify Worker as Agent Tool
- Worker definition becomes tool definition with `type: agent`
- Remove separate worker loading path
- `llm_agent()` implementation uses existing agent loop

### Phase 3: Remove Sandbox Layer
- Remove `SandboxConfig` from types
- Simplify filesystem toolset (no path validation)
- Document container-based isolation

### Phase 4: Simplify Workshop
- Workshop becomes directory of tool definitions
- Remove workshop-level sandbox config
- Convention over configuration

## Open Questions

- Recursion depth limits? (configurable max depth in context)
- Should `llm_ask` use same model as parent or allow override?
- How to visualize/debug deep call trees?
- Timeout handling for deeply nested calls?
