# Tool Entry Point (Neuro-Symbolic Unification Phase 2)

## Prerequisites

- [x] workers-as-tools.md - Workers exposed as tools to LLMs
- [x] 105-custom-tool-context.md - Opt-in context injection for custom tools

## Goal

Entry point is a tool, not a worker. The `main` tool can be either deterministic code (`tools.py::main`) or an LLM agent (`main.worker`). Completes the unification where everything is a tool.

## Background

**Current state:**
- Entry point is always a worker (LLM agent)
- CLI loads `main.worker` and runs PydanticAI agent
- Deterministic code can only be called *by* workers, not *as* entry points

**Target state:**
- Entry point is the `main` tool
- `main` can be defined as:
  - `main()` function in `tools.py` → deterministic entry point
  - `main.worker` file → LLM-powered entry point
- Both exist → error (no ambiguity)
- Both get unified `ToolContext` with `call_tool()` method

## The Spectrum (Updated)

```
Entry Point
     │
     ▼
   "main" tool
     │
     ├── tools.py::main()     (deterministic)
     │         │
     │         └── can call_tool("analyzer", ...)
     │                    │
     │                    ├── code tool
     │                    └── worker (LLM tool)
     │
     └── main.worker          (LLM-powered)
               │
               └── can call tools (code or workers)
```

## Key Design Decisions

### Tool Discovery Unification

A single resolver finds tools from both sources:
- Functions in `tools.py` (by function name)
- `.worker` files (by worker name)

Name collision between the two → error at discovery time.

### Unified Context

`ToolContext` provides `call_tool()` that works for any tool type:

```python
class ToolContext(Protocol):
    async def call_tool(self, name: str, input: str) -> str: ...
    # Also: depth, approval_controller, etc.
```

The caller doesn't know or care if the target is code or LLM.

### Custom Tools Context Opt-in

Custom tools in `tools.py` can optionally receive context via an opt-in decorator.
Simple tools stay unchanged; context-aware tools can call `ctx.call_worker(...)`
and later `ctx.call_tool(...)` once unified.

Context parameters are injected at runtime and excluded from the JSON schema so the
LLM never supplies them.

### Entry Point Resolution

```python
def resolve_entry_tool(name: str = "main") -> Tool:
    code_tool = find_in_tools_py(name)
    worker_tool = find_worker_file(name)

    if code_tool and worker_tool:
        raise ConfigError(f"Ambiguous: both tools.py::{name} and {name}.worker exist")

    return code_tool or worker_tool or raise NotFoundError(...)
```

### Signature for Code Entry Tools

```python
# tools.py
async def main(ctx: ToolContext, input: str) -> str:
    """Entry point - orchestrates other tools."""
    analysis = await ctx.call_tool("analyzer", input)
    summary = await ctx.call_tool("summarizer", analysis)
    return summary
```

## Tasks

### Phase 1: Unified Tool Registry

Create a registry that knows about both code tools and workers:

- [ ] Create `ToolRegistry` class (or extend existing registry)
- [ ] `find_tool(name)` returns a `Tool` (code or worker)
- [ ] `Tool` abstraction with `kind: Literal["code", "worker"]`
- [ ] Detect and error on name collisions at discovery time
- [ ] Handle search paths: project `tools.py`, `.worker` files, builtins

### Phase 2: call_tool Unification

Replace `call_worker` with unified `call_tool`:

- [ ] Add `call_tool(name, input)` method to `ToolContext` Protocol
- [ ] Implementation dispatches based on tool kind:
  - Code tool → call function directly
  - Worker → delegate to existing `call_worker_async`
- [ ] Deprecate or alias `call_worker` → `call_tool`
- [ ] Update existing tools that use `call_worker`

### Phase 3: Entry Point Execution

Change CLI to run tools instead of workers:

- [ ] `run_tool_async(name, input, ...)` as new entry point
- [ ] For code tools: instantiate context, call function
- [ ] For workers: delegate to existing `run_worker_async`
- [ ] CLI `--worker` flag → `--tool` (or keep for compat, map internally)
- [ ] Default entry point remains `main`

### Phase 4: Context for Code Entry Tools

Ensure code tools get full context when run as entry point:

- [ ] Create `ToolContext` instance with:
  - `call_tool` method
  - `registry` access
  - `approval_controller`
  - `depth` tracking
  - `message_callback` for streaming events
- [ ] Same context structure whether tool is entry point or called nested

### Phase 5: Cleanup

- [ ] Update documentation to reflect tool-first model
- [ ] Update examples to show code entry points
- [ ] Ensure error messages are clear ("both tools.py::main and main.worker exist")

## Architecture

```
CLI
 │
 ▼
resolve_entry_tool("main")
 │
 ├─ tools.py::main() found ────▶ run as code tool
 │                                    │
 │                                    ├── ctx.call_tool("analyzer")
 │                                    │        │
 │                                    │        └── code or worker
 │                                    │
 │                                    └── return result
 │
 └─ main.worker found ─────────▶ run as worker (existing flow)
                                      │
                                      └── LLM agent loop
                                             │
                                             └── calls tools
```

## Decisions

1. **Toolset configuration for code entry points**: No toolset config for code entry points. The registry exposes all code tools and workers; use a worker entry point if you need restricted toolsets.

2. **Approval for code entry tools**: No new approval gating for tool-to-tool calls. Approvals remain enforced by toolsets when an LLM invokes tools. The approval controller still flows into workers so their internal tool calls are gated as usual.

3. **Attachments**: No attachment policy for code entry points. Attachments (if provided) are exposed via context for explicit handling; they are not auto-injected into prompts. Workers still validate attachments against their own policies.

## Test Strategy

- Test `ToolRegistry` finds both code tools and workers
- Test name collision detection and error message
- Test code tool as entry point can `call_tool` to workers
- Test worker as entry point still works (regression)
- Test depth tracking works across code→worker→code chains
- Integration test: full orchestration via code entry point

## Implementation Notes

### Tool Discovery + Registry

- Use `WorkerRegistry.list_workers()` for all worker names (includes built-ins + generated).
- Add a helper to locate project `tools.py` even if `main.worker` does not exist; do not reuse `find_custom_tools("main")` because it short-circuits when the worker is missing.
- Tools discovery should only include functions defined in the module (`func.__module__ == module.__name__`) and skip private names starting with `_`.
- Suggested API: `ToolRegistry.resolve(name)` -> `Tool(kind="code"|"worker", handler=callable|worker_name, source_path=Path)`.
- Collision checks: code tool name vs worker name -> error at discovery time (before execution).

### Tool Invocation

- `call_tool_async(name, input, ctx)` dispatches by tool kind:
  - Code tool: call sync or await async; pass `ctx` only if the tool is marked with the opt-in decorator from `105-custom-tool-context.md`.
  - Worker tool: delegate to `call_worker_async` (or `run_worker_async`) and pass through `approval_controller`, `message_callback`, `creation_defaults`, `cli_model`, `attachments`, and `depth`.
- Keep `call_worker` as a thin wrapper or alias to `call_tool` but prefer `call_tool` everywhere.

### Entry Tool Execution + CLI

- Add `run_tool_async(...)` in `llm_do/runtime.py` (mirror `run_worker_async` signature, but `tool` name) and re-export in `llm_do/base.py`.
- For code tools, return `WorkerRunResult(output=..., messages=[])` to keep CLI output handling unchanged.
- Rename CLI flag to `--tool` and update `tests/test_cli_async.py` (avoid keeping `--worker` for backcompat).

### Context for Code Tools

- Define a minimal `ToolExecutionContext` that implements `ToolContext`:
  - `registry`, `approval_controller`, `creation_defaults`, `message_callback`, `cli_model`, `attachments`, `depth`, `cost_tracker`
  - `call_tool()` uses `ToolRegistry` and applies the dispatch rules above.
- Extend `ToolContext` Protocol if needed to expose `attachments` to code entry tools.

### Tests to Add/Update

- New: tool registry discovery + collision tests (code tool vs worker, tools.py without main.worker).
- Update `tests/test_custom_tools.py` for context-aware tools (opt-in decorator path).
- Update `tests/test_cli_async.py` for `--tool` entry point.

## Current State

Design agreed. Implementation not started. Open questions resolved (toolsets, approvals, attachments).

Context injection for custom tools is complete (opt-in decorator, schema omission,
runtime injection).

## References

- Prior work: `docs/tasks/completed/workers-as-tools.md`
- Design notes: `docs/notes/neuro-symbolic-tool-unification.md`
- Current runtime: `llm_do/runtime.py`
- Current types: `llm_do/types.py`
- Current CLI: `llm_do/cli_async.py`
