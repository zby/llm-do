# Architecture

This document covers the internal architecture of llm-do: worker definitions, runtime flow, and module organization.

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

### Lifecycle

1. **Definition** - `.worker` file describes instructions, toolsets, model
2. **Loading** - `worker_file.load_worker_file()` parses frontmatter and instructions
3. **Resolution** - `cli.main.build_entry()` resolves toolsets and builds `Worker`/`ToolInvocable`
4. **Run Boundary** - `runtime.run_entry()` applies `ApprovalPolicy` (`wrap_entry_for_approval`) and constructs `WorkerRuntime`
5. **Execution** - `WorkerRuntime.run()` dispatches; `Worker` builds a PydanticAI `Agent` and runs it
6. **Result** - Final output is returned (usage tracked in `WorkerRuntime`)

### Key Capabilities

**1. Worker-to-Worker Delegation**

Workers delegate by declaring other worker names in `toolsets`:
- Worker entries are exposed as tools
- Nested calls are tracked in `WorkerRuntime.depth` (default max depth: 5)
- Toolsets are not inherited; each worker declares its own
- Nested worker calls start with a clean message history; only the top-level run uses chat history

**2. Tool Approval System**

Toolsets are wrapped by `ApprovalToolset`:
- Built-in toolsets implement `needs_approval()` for per-call decisions
- TUI session approvals are cached in the approval callback wrapper (`remember="session"`)
- Wrapping is applied at the run boundary (`run_entry()` → `wrap_entry_for_approval()`), configured via `ApprovalPolicy`
- `--approve-all` bypasses prompts for automation
- `--reject-all` denies approval-required tools without prompting

Approval boundary:
- Approvals gate tool calls initiated during a run (LLM tool calls or code calling `ctx.deps.call`).
- The entry invocable itself is trusted when invoked from code; code-entry tools are not approval-gated.
- If a programmatic entry should be gated, wrap that toolset with `ApprovalToolset` before running or route through a worker that calls it as a tool.

**3. Built-in Toolsets**

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
│   ├── approval.py     # ApprovalPolicy + wrapping helpers
│   ├── context.py      # WorkerRuntime dispatcher and depth tracking
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

## Execution Flow

```
llm-do CLI
    |
    v
load_worker_file() + discovery.load_toolsets_and_workers_from_files()
    |
    v
cli.main.build_entry() -> Worker or ToolInvocable
    |
    v
run_entry() = wrap_entry_for_approval() + WorkerRuntime.from_entry() + WorkerRuntime.run()
    |
    v
Worker builds Agent -> agent.run() or run_stream()
    |
    v
final output
```

### Nested Execution

Worker tool calls use the same dispatcher as code entry points:

```
Worker A (depth=0)
    |
    v
LLM calls tool "analyzer" (Worker)
    |
    v
Worker B (depth=1)
```

Code entry points can call tools directly:

```python
result = await ctx.deps.call("analyzer", {"input": "..."})
```

WorkerRuntime state (model, depth, usage, events) flows down the call tree.

---

## Programmatic Usage

For direct Python runs (without the CLI), resolve an entry and run it via the same run boundary:

```python
from llm_do.runtime import ApprovalPolicy, run_entry
from llm_do.cli.main import build_entry

entry = await build_entry(
    worker_files=["main.worker"],
    python_files=["tools.py"],
    entry_name="main",
)

result, _ctx = await run_entry(
    entry=entry,
    prompt="Hello",
    approval_policy=ApprovalPolicy(mode="approve_all"),
)
```

In non-interactive contexts, use `ApprovalPolicy(mode="approve_all")` (or provide an `approval_callback`) to avoid permission errors for approval-required tools.
