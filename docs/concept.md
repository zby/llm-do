# llm-do: Concept and Design

## Core Idea

**Workers are functions.**

LLM workflows compose focused workers. Each worker does one thing well with tight context—no bloated multi-purpose prompts.

| Programming | llm-do |
|-------------|--------|
| Project directory | Registry root |
| Function | `.worker` file |
| Function call | `_worker_*` tool |

A **worker** is a prompt template + configuration + tools, packaged as an executable unit that the LLM interprets.

## What Is a Worker?

A **worker** is an executable prompt artifact: a persisted configuration that defines *how* to run an LLM-backed task (instructions, tools, attachments, models, outputs) rather than *what code to call*.

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

## Project Structure

Workers live at the project root:

```
my-project/
├── orchestrator.worker       # Entry point
├── analyzer.worker           # Helper worker
├── formatter/                # Directory-form worker
│   ├── worker.worker
│   └── tools.py              # Worker-specific tools
├── tools.py                  # Shared Python tools (optional)
├── templates/                # Shared Jinja templates (optional)
├── input/                    # Input directory (convention)
└── output/                   # Output directory (convention)
```

Run workers from the project directory:
```bash
cd my-project
llm-do --worker orchestrator "Process the input files"
```

### Lifecycle

1. **Definition** - `.worker` file describes instructions, tool policies, attachment rules
2. **Loading** - Registry resolves prompts, validates configuration
3. **Invocation** - Runtime builds execution context (approvals, tools, attachments)
4. **Execution** - PydanticAI agent runs with worker's instructions and constraints
5. **Result** - Structured output with message logs

### Why Workers? (vs PydanticAI Agents)

| Worker | PydanticAI Agent |
| --- | --- |
| Persistent artifact (YAML) | In-memory runtime object |
| Encodes policy (tool approvals, attachment rules) | No built-in policy layer |
| LLMs can create/edit workers | No persistence semantics |
| Version-controllable, lockable | Managed by developer code |
| Structured execution results | Returns agent output |

**The worker abstraction sits *above* the agent**: it packages the rules and artifacts that make an agent safe, repeatable, and composable.

## Why This Matters

**The LLM context problem**: LLM behavior is context-sensitive. Unlike traditional compilers where unused code is ignored, adding more text to an LLM prompt can degrade results. Large prompts bloat, drift, and fail unpredictably. When you batch everything into a single prompt, the LLM loses focus.

**The solution**: Workers with isolated contexts, connected through three mechanisms:

1. **Worker delegation** (`_worker_*` tools) — Decompose workflows into focused sub-calls. Each worker handles one unit of work with its own instructions, model, and tools. No bloated catch-all prompts.

2. **Autonomous worker creation** (`worker_create`) — Workers propose specialized sub-workers when needed. This is same-language metaprogramming: the LLM that executes workers also writes them. Created definitions are saved to disk for review.

3. **Progressive hardening** — Refine created workers over time: edit prompts, add schemas, lock allowlists, extract logic to Python. Orchestrators delegate to vetted workers instead of fragile inline instructions.

**What this enables**:
- **Composability**: Recursive calls feel like function calls, not orchestration glue
- **Autonomy**: Workers identify when they need specialized handlers and create them
- **Control**: Approval gates, container boundary, progressive refinement
- **Reproducibility**: Every sub-call is explicit, loggable, auditable

## Key Capabilities

Four primitives implement these mechanisms:

### 1. Filesystem Toolset (Container Boundary)
Workers read/write files through the filesystem toolset. There is no path sandboxing;
llm-do relies on a container boundary for isolation.
- `toolsets.filesystem.read_approval` gates `read_file`
- `toolsets.filesystem.write_approval` gates `write_file`
- `list_files` is always pre-approved

### 2. Worker-to-Worker Delegation
Workers delegate to other workers via `_worker_*` tools (e.g., `_worker_analyzer`, `_worker_formatter`):
- Delegation config maps worker names to tools in `toolsets.delegation`
- Attachments are validated against the callee's `attachment_policy`
- Model resolution is per-worker (CLI model > worker model > env var); no implicit inheritance
- Nested calls are capped (default depth 5)
- Tool access NOT inherited—each worker declares its own
- Results can be structured (validated JSON) or freeform text

Tools can also call workers directly via `ToolContext` (`RunContext[ToolContext]`
and `ctx.deps.call_worker(...)`) to build hybrid tools.

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
- Created workers start with minimal toolsets and attachment policy (principle of least privilege)
- Saved definition is immediately executable and refinable

## Worker-Tool Unification

**Workers and tools are the same abstraction.** A worker is a tool whose implementation is an LLM agent loop. This unification enables seamless interleaving of neural (LLM) and symbolic (deterministic code) components.

**Two integration points:**
- **Workers as tools**: Each delegated worker appears as a `_worker_*` tool that the LLM can call like any other tool
- **Tools calling workers**: Python tools can invoke workers via `ToolContext.call_worker()` for nested LLM reasoning

This creates **dual recursion**:
```
LLM ──calls──▶ Tool ──calls──▶ LLM ──calls──▶ Tool ...
     reason         execute         reason
     decide         compute         decide
```

| Component | Strengths |
|-----------|-----------|
| Neural (LLM) | Flexible reasoning, handles ambiguity, contextual |
| Symbolic (Tool) | Deterministic, precise, cheap, auditable |

The unified interface means refactoring between neural and symbolic is just changing which component handles a task—no architectural changes required.

## Progressive Hardening (and Softening)

The worker-tool unification enables **bidirectional refactoring**:

### Hardening: Neural → Symbolic

Workers start flexible, then harden as patterns stabilize:

1. **Autonomous creation** — Worker creates sub-worker, user approves saved definition
2. **Testing** — Run tasks, observe behavior
3. **Iteration** — Edit definition: refine prompts, add schemas, tune models
4. **Locking** — Pin orchestrators to vetted workers via allowlists
5. **Migration** — Extract deterministic operations to tested Python

**Example** (hardening):
- **Day 1**: Orchestrator creates `evaluator`, user approves
- **Week 1**: Test runs reveal drift, refine prompt
- **Week 2**: Add structured output schema
- **Week 3**: Extract scoring logic to Python toolbox with tests
- **Week 4**: Worker calls `compute_score()`, math is now deterministic

### Softening: Symbolic → Neural

When rigid code needs more flexibility, replace deterministic logic with worker calls:

**Example** (softening):
- A Python tool parses config files with regex
- Edge cases multiply, regex becomes unmaintainable
- Replace parsing with `ctx.deps.call_worker("config_parser", raw_text)`
- The worker handles ambiguous formats with LLM reasoning
- Deterministic validation still runs on the parsed output

### The Hybrid Pattern

Hardening often produces **hybrid tools**—Python functions that handle deterministic logic but delegate fuzzy parts to smaller, focused workers:

```python
async def evaluate_document(ctx: RunContext[ToolContext], path: str) -> dict:
    # Deterministic: load and validate
    content = load_file(path)
    if not validate_format(content):
        raise ValueError("Invalid format")

    # Neural: delegate ambiguous analysis to focused worker
    analysis = await ctx.deps.call_worker("content_analyzer", content)

    # Deterministic: compute final score
    return {"score": compute_score(analysis), "analysis": analysis}
```

This is the middle ground on the spectrum—tested Python for the predictable parts, LLM reasoning only where needed.

### The Refactoring Spectrum

```
Pure Python ◄─────────────────────────► Pure Worker
(all symbolic)                          (all neural)

  compute_hash ── smart_refactor ── code_reviewer
       │               │                   │
       │         hybrid: mostly            │
       │         deterministic,       full LLM
       │         calls LLM when stuck      │
       │                                   │
   no LLM ◄───────────────────────────► only LLM
```

Any component can slide along this spectrum as requirements evolve. The unified interface makes this refactoring straightforward.

## Design Principles

1. **Workers as functions** — Focused, composable units that do one thing well

2. **Workers as artifacts** — Saved to disk, version controlled, auditable, refinable by programmers

3. **Guardrails by construction** — Attachment validation and approval enforcement happen in code, guarding against LLM mistakes (not security against attackers)

4. **Explicit configuration** — Tool access and worker allowlists declared in definitions, not inherited

5. **Recursive composability** — Workers calling workers should feel like function calls

6. **Bidirectional refactoring** — Harden workers to Python as patterns stabilize; soften rigid code to worker calls when flexibility is needed

## Architecture Overview

Built on [PydanticAI](https://ai.pydantic.dev/) for agent runtime and structured outputs.

**Core modules**:
- `runtime.py` — Worker orchestration, delegation, creation lifecycle
- `toolset_loader.py` — Tool registration (filesystem, delegation, custom tools)
- `execution.py` — Agent runners and execution context
- `types.py` — Type definitions and data models (WorkerContext, ToolContext)
- `registry.py` — Worker definition loading and persistence
- `filesystem_toolset.py` — File operations (container boundary)
- `delegation_toolset.py` — Worker delegation tools
- `attachments/` — Attachment policy and payload types

**Key patterns**:
- Protocol-based DI enables recursive worker calls without circular imports
- Security boundaries enforced in code (attachments, approvals) and via container isolation
- Workers as first-class executables with standard invocation

See [`architecture.md`](architecture.md) for implementation details.
