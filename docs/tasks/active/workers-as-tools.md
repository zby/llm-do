# Workers as Tools (Neuro-Symbolic Unification Phase 1)

## Goal

Unify workers and tools: a worker is just a tool whose implementation is an LLM agent loop. This is the first step toward neuro-symbolic tool unification.

See `docs/notes/neuro-symbolic-tool-unification.md` for full design.

## Background

**Current state:**
- Workers and tools are separate concepts
- Workers called via `worker_call(worker="name", input_data="...")`
- Tools are deterministic functions

**Target state:**
- Everything is a tool
- Workers are tools with `type: agent`
- Tools receive `ToolContext` enabling nested LLM calls
- Direct invocation: `code_reviewer(input="...")` instead of `worker_call`

## The Spectrum

```
Pure Tool ←————————————————————→ Agent Tool (Worker)
(all symbolic)                   (all neural)

read_file ──── smart_refactor ──── code_reviewer
   │                 │                   │
no LLM         calls LLM            full LLM
               when needed          agent loop
```

## Tasks

### Phase 1: ToolContext Foundation

Add context that flows through all tool calls:

```python
class ToolContext:
    cost_tracker: CostTracker
    approval_controller: ApprovalController
    depth: int  # nesting depth

    async def llm_ask(self, prompt: str) -> str: ...
    async def llm_agent(self, system: str, tools: list, input: Any) -> Any: ...
    async def call_tool(self, name: str, args: dict) -> Any: ...
```

- [ ] Define `ToolContext` class
- [ ] Pass context through existing tool calls
- [ ] Existing tools ignore new context (backwards compatible)

### Phase 2: Agent Tool Type

Support `type: agent` in tool definitions:

```yaml
name: code-reviewer
type: agent
model: claude-sonnet-4
tools: [read_file, grep, glob]
---
You are a senior code reviewer...
```

- [ ] Add `type` field to tool/worker definition schema
- [ ] `type: agent` means implementation is `ctx.llm_agent()`
- [ ] `type: function` (default) means Python function

### Phase 3: WorkerToolset → AgentToolset

Rename and simplify:

- [ ] Rename `DelegationToolset` to `AgentToolset`
- [ ] Generate tool per allowed agent (not generic `worker_call`)
- [ ] Tool schema from agent's input/output schema
- [ ] Remove `worker_call` indirection

**Before:**
```
LLM sees: worker_call(worker="summarizer", input_data="...")
```

**After:**
```
LLM sees: summarizer(input="...")
```

### Phase 4: Implement Nested LLM Calls

- [ ] `ctx.llm_ask()` - quick question to LLM (uses parent model)
- [ ] `ctx.llm_agent()` - full agent loop (what agent tools use)
- [ ] Context carries cost/approvals through nested calls
- [ ] Depth tracking and limits

### Phase 5: Remove Sandbox Layer

Container isolation replaces per-worker sandbox:

- [ ] Remove `SandboxConfig` from types
- [ ] Simplify filesystem toolset (no path validation)
- [ ] Remove `pydantic_ai_filesystem_sandbox` or make trivial
- [ ] Update documentation

### Phase 6: Simplify Workshop

- [ ] Remove `sandbox` from `WorkshopConfig`
- [ ] Workshop becomes directory of tool definitions
- [ ] Convention over configuration

## Architecture

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

Context flows down: cost_tracker, approval_controller, depth
```

## Tool Definition Format

```yaml
# Pure tool - references Python function
name: read_file
type: function
function: llm_do.tools.filesystem:read_file

---

# Agent tool (worker) - LLM agent loop
name: code-reviewer
type: agent
model: claude-sonnet-4
tools: [read_file, grep, glob]
---
You are a senior code reviewer...
```

## Open Questions

1. **Naming conflicts**: What if agent name conflicts with another tool?
   - Recommendation: Error on conflict (explicit is better)

2. **Recursion limits**: Max nesting depth?
   - Recommendation: Configurable, default 5

3. **Model for `llm_ask`**: Same as parent or allow override?
   - Recommendation: Same as parent, cheaper model option later

4. **Attachments**: Keep or simplify?
   - Recommendation: Simplify — container handles file access

## Current State

Not started.

## References

- Design: `docs/notes/neuro-symbolic-tool-unification.md`
- Current delegation: `llm_do/delegation_toolset.py`
- Worker execution: `llm_do/runtime.py`
