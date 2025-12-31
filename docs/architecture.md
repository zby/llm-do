# Architecture

This document covers the internal architecture of llm-do: worker definitions, context runtime flow, and module organization.

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
3. **Resolution** - `ctx_runtime.build_entry()` resolves toolsets and builds `WorkerEntry`/`ToolEntry`
4. **Context** - `Context.from_entry()` selects the effective model and assembles the runtime
5. **Execution** - `WorkerEntry` builds a PydanticAI `Agent` and runs it
6. **Result** - Final output is returned (usage tracked in `Context`)

### Key Capabilities

**1. Worker-to-Worker Delegation**

Workers delegate by declaring other worker names in `toolsets`:
- Worker entries are exposed as tools
- Nested calls are tracked in `Context.depth` (default max depth: 5)
- Toolsets are not inherited; each worker declares its own

**2. Tool Approval System**

Toolsets are wrapped by `ApprovalToolset`:
- Built-in toolsets implement `needs_approval()` for per-call decisions
- TUI session approvals are cached in the approval callback wrapper (`remember="session"`)
- `--approve-all` bypasses prompts for automation
- `--reject-all` denies approval-required tools without prompting

**3. Built-in Toolsets**

llm-do ships with:
- **filesystem**: `read_file`, `write_file`, `list_files`
- **shell**: command execution with whitelist-based approval rules

Python toolsets are discovered from `.py` files using `FunctionToolset` (or any `AbstractToolset`).

---

## Module Structure

```
llm_do/
├── ctx_runtime/
│   ├── cli.py          # llm-do entry point
│   ├── ctx.py          # Context dispatcher and depth tracking
│   ├── entries.py      # WorkerEntry and ToolEntry
│   ├── worker_file.py  # .worker parser
│   ├── discovery.py    # Load toolsets/entries from .py files
│   ├── builtins.py     # Built-in toolset registry
│   └── __init__.py
├── filesystem_toolset.py
├── shell/              # Shell toolset implementation
├── ui/                 # UI events and display backends
├── config_overrides.py # --set parsing and application
├── model_compat.py     # Model selection and compatibility checks
└── oauth_cli.py        # llm-do-oauth helper
```

---

## Execution Flow

```
llm-do CLI
    |
    v
load_worker_file() + discovery.load_toolsets_from_files()
    |
    v
build_entry() -> WorkerEntry or ToolEntry
    |
    v
wrap toolsets with ApprovalToolset
    |
    v
Context.from_entry()
    |
    v
Context.run(entry, {"input": prompt})
    |
    v
WorkerEntry builds Agent -> agent.run() or run_stream()
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
LLM calls tool "analyzer" (WorkerEntry)
    |
    v
Worker B (depth=1)
```

Code entry points can call tools directly:

```python
result = await ctx.deps.call("analyzer", {"input": "..."})
```

Context state (model, approvals, depth, usage, events) flows down the call tree.
