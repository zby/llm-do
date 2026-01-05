# Architecture

This document covers the internal architecture of llm-do: worker definitions, runtime scopes, and execution flow.

For high-level concepts, see [`concept.md`](concept.md).

---

## Worker Fundamentals

### What Is a Worker?

A **worker** is an executable prompt artifact: a persisted configuration that defines how to run an LLM-backed task (instructions, toolsets, models) rather than what code to call.

Workers live as `.worker` files (YAML frontmatter + instructions) and can be:
- Created by humans or LLMs
- Version-controlled like source code
- Composed (workers can call other workers)

### Worker File Format

```yaml
---
name: main
model: anthropic:claude-haiku-4-5
toolsets:
  shell: {}
  filesystem: {}
  my_tools: {}
  analyzer: {}
server_side_tools:
  - tool_type: web_search
---
Instructions for the worker...
```

- `toolsets` maps names to configuration. Names refer to built-ins, Python toolsets, or other workers.
- `server_side_tools` enables PydanticAI builtin tools (web search, fetch, code execution, image generation).
- Toolsets can also be declared by fully-qualified class path (plugin-style loading).

### Project Structure

```
my-project/
├── main.worker            # Entry worker
├── analyzer.worker        # Helper worker
├── tools.py               # Python toolsets (optional)
├── input/                 # Input directory (convention)
└── output/                # Output directory (convention)
```

---

## Runtime Scopes

The runtime has two distinct scopes, analogous to a web server:

| llm-do | Web Server | Lifetime | Shared? |
|--------|------------|----------|---------|
| **RuntimeConfig** | Server config (port, middleware, DB pool) | Entire run | Yes - all workers see same config |
| **CallFrame** | Request context (headers, session, body) | Single worker call | No - each worker gets its own |

### Why This Matters

When a worker spawns a child worker (like a web server making a subrequest to another service):
- They share the **same RuntimeConfig** (same approval policy, same event sink, same usage collector)
- They have **separate CallFrames** (different depth, different messages, potentially different model)

This separation ensures:
1. **Isolation** - A child worker's internal conversation doesn't pollute the parent's message history
2. **Shared observability** - All workers report to the same usage collector and event sink
3. **Consistent policy** - Approval rules apply uniformly across the entire call tree

### The Three Runtime Types

```
RuntimeConfig (frozen, shared)       CallConfig (frozen, per-worker)
├── cli_model                        ├── toolsets (tuple)
├── run_approval_policy              ├── model (resolved)
├── max_depth                        └── depth
├── on_event
├── verbosity                        CallFrame (mutable state)
├── usage (UsageCollector)           ├── config: CallConfig
└── message_log (MessageAccumulator) ├── prompt
                                     └── messages (list)
         └───────────────┬───────────────┘
                         │
                 WorkerRuntime (facade)
```

**RuntimeConfig** - Global configuration, immutable, shared across all workers in a run:
- `cli_model` - Model override from CLI (if any)
- `run_approval_policy` - How to handle tool approval requests
- `max_depth` - Maximum worker nesting depth
- `on_event` - Callback for UI events (tool calls, streaming text)
- `usage` - Collects token usage from all workers
- `message_log` - Diagnostic sink for all messages (testing/logging only)

**CallConfig** - Per-worker configuration, frozen at fork time:
- `toolsets` - Tools available to this worker (immutable tuple)
- `model` - Resolved model for this worker
- `depth` - Current nesting depth

**CallFrame** - Per-worker mutable state:
- `config` - The frozen CallConfig
- `prompt` - Current user prompt
- `messages` - Conversation history (isolated per worker)

**WorkerRuntime** - Facade combining config + frame, used as PydanticAI deps.

### Worker Isolation

Parent workers only see tool call/result from child workers, not their internal conversation:

```
Parent Worker (depth 1):
  messages = [UserPrompt, ToolCall(child), ToolResult, Response]
                         ↑ parent only sees this exchange

Child Worker (depth 2):
  messages = [UserPrompt, Response]  ← isolated, discarded after return
```

This is why `messages` stays in `CallFrame` (per-worker) rather than `RuntimeConfig` (global). The `MessageAccumulator` in RuntimeConfig is a write-only diagnostic sink for testing - workers don't read from it.

---

## Worker Lifecycle

1. **Definition** - `.worker` file describes instructions, toolsets, model
2. **Loading** - `worker_file.load_worker_file()` parses frontmatter and instructions
3. **Resolution** - `cli.main.build_entry()` resolves toolsets and builds `Worker`/`ToolInvocable`
4. **Run Boundary** - `runtime.run_entry()` constructs `WorkerRuntime` with `RunApprovalPolicy` and wraps toolsets for approval gating
5. **Execution** - `WorkerRuntime.run()` dispatches; `Worker` builds a PydanticAI `Agent` and runs it
6. **Result** - Final output is returned (usage tracked in `RuntimeConfig.usage`)

### Execution Flow

```
llm-do CLI
    │
    ▼
load_worker_file() + discovery.load_toolsets_and_workers_from_files()
    │
    ▼
cli.main.build_entry() → Worker or ToolInvocable
    │
    ▼
run_entry() = wrap_entry_for_approval() + WorkerRuntime.from_entry() + WorkerRuntime.run()
    │
    ▼
Worker builds Agent → agent.run() or run_stream()
    │
    ▼
final output
```

### Nested Execution

When a worker calls another worker as a tool:

```
Worker A (depth=0)
    │
    ▼
LLM calls tool "analyzer" (Worker)
    │
    ▼
Worker B (depth=1) ← new CallFrame, shared RuntimeConfig
```

The child worker:
- Gets a fresh `CallFrame` with incremented depth and empty messages
- Shares the parent's `RuntimeConfig` (same approval policy, usage collector, events)
- Returns only its final result to the parent (internal messages discarded)

Code entry points can also call tools directly:

```python
result = await ctx.deps.call("analyzer", {"input": "..."})
```

---

## Key Capabilities

### Worker-to-Worker Delegation

Workers delegate by declaring other worker names in `toolsets`:
- Worker entries are exposed as tools
- Nested calls are tracked in `CallFrame.depth` (default max depth: 5)
- Toolsets are not inherited; each worker declares its own
- Nested worker calls start with a clean message history; only the top-level run uses chat history

### Tool Approval System

Toolsets are wrapped by `ApprovalToolset`:
- Built-in toolsets implement `needs_approval()` for per-call decisions
- TUI session approvals are cached in the approval callback wrapper (`remember="session"`)
- Wrapping is applied at worker call time (`Worker.call` → `WorkerApprovalPolicy.wrap_toolsets()`)
- `--approve-all` bypasses prompts for automation
- `--reject-all` denies approval-required tools without prompting

Approval boundary:
- Approvals gate tool calls initiated during a run (LLM tool calls or code calling `ctx.deps.call`)
- The entry invocable itself is trusted when invoked from code; code-entry tools are not approval-gated
- If a programmatic entry should be gated, wrap that toolset with `ApprovalToolset` before running

### Built-in Toolsets

llm-do ships with:
- **filesystem**: `read_file`, `write_file`, `list_files`
- **shell**: command execution with whitelist-based approval rules

Built-ins can be referenced by short alias (`shell`, `filesystem`) or by class path
(e.g. `llm_do.toolsets.shell.ShellToolset`).

Python toolsets are discovered from `.py` files using `FunctionToolset` (or any `AbstractToolset`).

---

## Module Structure

```
llm_do/
├── cli/                # CLI entry points
│   ├── main.py         # llm-do CLI + entry resolution
│   └── oauth.py        # llm-do-oauth helper
├── runtime/            # Core runtime
│   ├── runner.py       # run_entry execution boundary
│   ├── approval.py     # RunApprovalPolicy + WorkerApprovalPolicy + wrapping helpers
│   ├── context.py      # RuntimeConfig, CallConfig, CallFrame, WorkerRuntime
│   ├── contracts.py    # Protocols (Invocable, WorkerRuntimeProtocol)
│   ├── worker.py       # Worker and ToolInvocable
│   ├── worker_file.py  # .worker parser
│   ├── discovery.py    # Load toolsets/entries from .py files
│   └── __init__.py
├── toolsets/           # Toolset implementations and loading
│   ├── loader.py       # Toolset class-path loader
│   ├── builtins.py     # Built-in toolset registry
│   ├── filesystem.py
│   └── shell/          # Shell toolset package
├── ui/                 # UI events and display backends
├── config.py           # --set parsing and application
└── models.py           # Model selection and compatibility checks
```

---

## Programmatic Usage

For direct Python runs (without the CLI), resolve an entry and run it via the same run boundary:

```python
from llm_do.runtime import RunApprovalPolicy, run_entry
from llm_do.cli.main import build_entry

entry = await build_entry(
    worker_files=["main.worker"],
    python_files=["tools.py"],
    entry_name="main",
)

result, _ctx = await run_entry(
    entry=entry,
    prompt="Hello",
    approval_policy=RunApprovalPolicy(mode="approve_all"),
)
```

In non-interactive contexts, use `RunApprovalPolicy(mode="approve_all")` (or provide an `approval_callback`) to avoid permission errors for approval-required tools.
