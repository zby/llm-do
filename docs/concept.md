# llm-do: Concept and Design

## Core Idea

**Projects are programs. Workers are functions.**

Just like programs compose focused functions, LLM workflows compose focused workers. Each worker does one thing well with tight context—no bloated multi-purpose prompts.

| Programming | llm-do |
|-------------|--------|
| Program | Project directory |
| `main()` | `main.worker` |
| Function | `.worker` file |
| Function call | `worker_call` tool |

A **project** is a directory with a `main.worker` entry point. A **worker** is a prompt template + configuration + tools, packaged as an executable unit that the LLM interprets.

## What Is a Project?

A **project** is a directory that packages workers together:

```
my-project/
├── main.worker           # Entry point (required)
├── project.yaml          # Shared config (optional)
├── tools.py              # Project-wide Python tools (optional)
├── templates/            # Shared Jinja templates (optional)
├── workers/              # Helper workers (optional)
│   ├── analyzer.worker
│   └── formatter/
│       ├── worker.worker
│       └── tools.py      # Worker-specific tools
├── input/                # Input sandbox (convention)
└── output/               # Output sandbox (convention)
```

**Configuration inheritance**: `project.yaml` provides defaults (model, sandbox, toolsets) inherited by all workers. Workers can override.

## What Is a Worker?

A **worker** is an executable prompt artifact: a persisted configuration that defines *how* to run an LLM-backed task (instructions, tools, sandboxes, models, outputs) rather than *what code to call*.

Workers live as `.worker` files (YAML front matter + instructions) and can be:
- Created by humans or LLMs
- Version-controlled like source code
- Locked to prevent accidental edits
- Composed (workers can call other workers)

**Two forms** with different trade-offs:

| Form | Path | Capabilities |
|------|------|--------------|
| **Single-file** | `name.worker` | Portable - one file, no dependencies. Built-in tools only. |
| **Directory** | `name/worker.worker` | Full power - custom Python tools (`tools.py`), Jinja templates. |

Single-file workers are intentionally limited to enable **truly portable LLM executables** - copy one `.worker` file and it works anywhere. For custom tools or worker-specific templates, use the directory model.

### Lifecycle

1. **Definition** - `.worker` file describes instructions, sandbox boundaries, tool policies
2. **Loading** - Registry resolves prompts, validates configuration
3. **Invocation** - Runtime builds execution context (sandboxes, approvals, tools)
4. **Execution** - PydanticAI agent runs with worker's instructions and constraints
5. **Result** - Structured output with message logs

### Why Workers? (vs PydanticAI Agents)

| Worker | PydanticAI Agent |
| --- | --- |
| Persistent artifact (YAML) | In-memory runtime object |
| Encodes security policy (sandbox, approvals) | No built-in policy layer |
| LLMs can create/edit workers | No persistence semantics |
| Version-controllable, lockable | Managed by developer code |
| Structured execution results | Returns agent output |

**The worker abstraction sits *above* the agent**: it packages the rules and artifacts that make an agent safe, repeatable, and composable.

## Why This Matters

**The LLM context problem**: LLM behavior is context-sensitive. Unlike traditional compilers where unused code is ignored, adding more text to an LLM prompt can degrade results. Large prompts bloat, drift, and fail unpredictably. When you batch everything into a single prompt, the LLM loses focus.

**The solution**: Workers with isolated contexts, connected through three mechanisms:

1. **Worker delegation** (`worker_call`) — Decompose workflows into focused sub-calls. Each worker handles one unit of work with its own instructions, model, and tools. No bloated catch-all prompts.

2. **Autonomous worker creation** (`worker_create`) — Workers propose specialized sub-workers when needed. This is same-language metaprogramming: the LLM that executes workers also writes them. Created definitions are saved to disk for review.

3. **Progressive hardening** — Refine created workers over time: edit prompts, add schemas, lock allowlists, extract logic to Python. Orchestrators delegate to vetted workers instead of fragile inline instructions.

**What this enables**:
- **Composability**: Recursive calls feel like function calls, not orchestration glue
- **Autonomy**: Workers identify when they need specialized handlers and create them
- **Control**: Approval gates, security boundaries (sandboxes, tool rules), progressive refinement
- **Reproducibility**: Every sub-call is explicit, loggable, auditable

## Key Capabilities

Four primitives implement these mechanisms:

### 1. Sandboxed File Access
Workers read/write files through explicitly configured sandboxes. Security by construction:
- Root directory and access mode (read-only or writable) declared per sandbox
- Path escapes (`..`, absolute paths) blocked by design
- File size limits prevent resource exhaustion
- Suffix filters control which file types can be read/written

### 2. Worker-to-Worker Delegation
The `worker_call` tool with enforcement layers:
- Allowlists restrict which workers can be called
- Attachment validation (count, size, extensions) happens before execution
- Model inheritance: worker definition → caller's model → CLI model → error
- Tool access NOT inherited—each worker declares its own
- Results can be structured (validated JSON) or freeform text

### 3. Tool Approval System
Configurable control over which operations require human approval:
- **Pre-approved**: Benign operations execute automatically
- **Approval-required**: Consequential operations require explicit user approval
- **Session approvals**: Approve once for repeated identical calls
- **Secure by default**: Custom tools require approval unless explicitly pre-approved

### 4. Autonomous Worker Creation
The `worker_create` tool, subject to approval:
- Worker proposes: name, instructions, optional schema/model
- User reviews definition, can edit or reject before saving
- Created workers start with minimal permissions (principle of least privilege)
- Saved definition is immediately executable and refinable

## Progressive Hardening

Workers start flexible, then harden as patterns stabilize:

1. **Autonomous creation** — Worker creates sub-worker, user approves saved definition
2. **Testing** — Run tasks, observe behavior
3. **Iteration** — Edit definition: refine prompts, add schemas, tune models
4. **Locking** — Pin orchestrators to vetted workers via allowlists
5. **Migration** — Extract deterministic operations to tested Python

**Example**:
- **Day 1**: Orchestrator creates `evaluator`, user approves
- **Week 1**: Test runs reveal drift, refine prompt
- **Week 2**: Add structured output schema
- **Week 3**: Extract scoring logic to Python toolbox with tests
- **Week 4**: Worker calls `compute_score()`, math is now deterministic

## Design Principles

1. **Projects as programs** — A project directory is the executable unit, `main.worker` is the entry point

2. **Workers as functions** — Focused, composable units that do one thing well

3. **Workers as artifacts** — Saved to disk, version controlled, auditable, refinable by programmers

4. **Guardrails by construction** — Sandboxes, attachment validation, approval enforcement happen in code, guarding against LLM mistakes (not security against attackers)

5. **Explicit configuration** — Tool access and worker allowlists declared in definitions, not inherited

6. **Recursive composability** — Workers calling workers should feel like function calls

7. **Progressive hardening** — Start with prompts for flexibility, extract deterministic logic to Python as patterns stabilize

## Architecture Overview

Built on [PydanticAI](https://ai.pydantic.dev/) for agent runtime and structured outputs.

**Core modules**:
- `runtime.py` — Worker orchestration, delegation, creation lifecycle
- `protocols.py` — Interface definitions for dependency injection
- `tools.py` — Tool registration (sandboxes, worker_call, worker_create, custom tools)
- `execution.py` — Agent runners and execution context
- `types.py` — Type definitions and data models
- `registry.py` — Worker definition loading and persistence
- `worker_sandbox.py` — Sandboxed filesystem operations

**Key patterns**:
- Protocol-based DI enables recursive worker calls without circular imports
- Security boundaries enforced in code (sandboxes, attachments, approvals)
- Workers as first-class executables with standard invocation

See [`architecture.md`](architecture.md) for implementation details.
