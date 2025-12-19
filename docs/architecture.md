# Architecture

This document covers the internal architecture of llm-do: worker definitions, runtime flow, and module organization.

For high-level concepts (neuro-symbolic computing, progressive hardening), see [`concept.md`](concept.md).

---

## Worker Fundamentals

### What Is a Worker?

A **worker** is an executable prompt artifact: a persisted configuration that defines *how* to run an LLM-backed task (instructions, tools, attachments, models, outputs) rather than *what code to call*.

Workers live as `.worker` files (YAML front matter + instructions) and can be:
- Created by humans or LLMs
- Version-controlled like source code
- Locked to prevent accidental edits
- Composed (workers can call other workers)

### Project Structure

Workers live at the project root:

```
my-project/
├── orchestrator.worker       # Entry point
├── analyzer.worker           # Helper worker
├── formatter.worker          # Another helper
├── tools.py                  # Shared Python tools (optional)
├── templates/                # Shared Jinja templates (optional)
├── input/                    # Input directory (convention)
└── output/                   # Output directory (convention)
```

### Lifecycle

1. **Definition** - `.worker` file describes instructions, tool policies, attachment rules
2. **Loading** - Registry resolves prompts, validates configuration
3. **Invocation** - Runtime builds execution context (approvals, tools, attachments)
4. **Execution** - PydanticAI agent runs with worker's instructions and constraints
5. **Result** - Structured output with message logs

### What Workers Add (over PydanticAI Agents)

Workers are a layer *above* PydanticAI agents. Each worker runs as a PydanticAI agent, but workers add:

- **Declarative config** — YAML files instead of Python code. Version-controllable, shareable, LLM-editable.
- **Delegation** — Workers call other workers like functions. PydanticAI agents don't compose out of the box.
- **Policy layer** — Tool approvals and attachment constraints enforced automatically.
- **Per-worker isolation** — Each worker has its own model, toolset, and context.

### Key Capabilities

**1. Worker-to-Worker Delegation**

Workers delegate via worker tools (e.g., `analyzer`, `formatter`):
- Delegation config maps worker names to tools in `toolsets.delegation`
- Attachments validated against callee's `attachment_policy`
- Model resolution per-worker (CLI model > worker model > env var)
- Nested calls capped at depth 5
- Tool access NOT inherited—each worker declares its own

**2. Tool Approval System**

Configurable control over which operations require human approval:
- **Pre-approved**: Benign operations execute automatically
- **Approval-required**: Consequential operations need explicit approval
- **Session approvals**: Approve once for repeated identical calls
- **Secure by default**: Custom tools require approval unless pre-approved

**3. Autonomous Worker Creation** *(experimental)*

The `worker_create` tool (subject to approval):
- Worker proposes: name, instructions, optional schema/model
- User reviews definition before saving
- Created workers start with minimal toolsets (least privilege)
- Saved definition is immediately executable

**4. Built-in Toolsets**

llm-do includes toolsets for common operations (more will be added):
- **Filesystem**: `read_file`, `write_file`, `list_files`
- **Shell**: Command execution with whitelist-based approval
- **Custom**: Python functions from `tools.py`

---

## Module Structure

```
llm_do/
├── runtime.py           # Worker execution and delegation
├── execution.py         # Agent execution strategies
├── model_compat.py      # Model compatibility validation
├── toolset_loader.py    # Dynamic toolset loading factory
├── types.py             # Type definitions and data models
├── registry.py          # Worker definition loading/persistence
├── attachments/         # Attachment policy and payload types
├── filesystem_toolset.py # File I/O tools
├── delegation_toolset.py # Worker delegation toolset
├── custom_toolset.py    # Custom Python tools toolset
├── shell/               # Shell toolset package
├── ui/                  # Display and UI components
├── cli_async.py         # Async CLI entry point
└── base.py              # Public API exports
```

**External packages**:
- `pydantic-ai-blocking-approval` — Synchronous tool approval system

---

## Execution Flow

```
CLI / run_worker_async()
        │
        ▼
┌─────────────────┐
│ WorkerRegistry  │ ← Load worker definition
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ WorkerContext   │ ← Build execution context (depth=0)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Toolsets        │ ← Build toolsets + approval wrappers
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PydanticAI      │ ← Create agent with tools
│ Agent           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ agent.run()     │ ← Execute with deps=context
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ WorkerRunResult │ ← Return output + messages
└─────────────────┘
```

### Nested Execution

When a tool calls `ctx.deps.call_worker()` or the LLM uses a worker delegation tool:

```
Worker A (depth=0)
    │
    ▼
┌─────────────────────────────────────────┐
│ LLM reasons, calls tool                 │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Tool executes                           │
│   - deterministic logic                 │
│   - ctx.deps.call_worker("B", input)  ──┼──┐
└─────────────────────────────────────────┘  │
                                             │
         ┌───────────────────────────────────┘
         ▼
    Worker B (depth=1)
        │
        ▼
    ┌─────────────────────────────────────┐
    │ LLM reasons, calls tools            │
    └────────┬────────────────────────────┘
             │
             ▼
        ... (up to MAX_WORKER_DEPTH=5)
```

Context flows down: approval controller and depth are shared across the call tree.
