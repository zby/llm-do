# llm-do: Concept and Design

## Core Idea

**Treat prompts as executables, with LLMs as the interpreter.**

Just like source code is packaged with build configs and dependencies to become executable programs, prompts need to be packaged with configuration (model, tools, schemas, security constraints) to become executable workers.

**Progressive hardening**: Start with flexible prompts that solve problems. But as systems grow and compose many parts, stochasticity becomes a liability—especially in key areas. So you progressively harden: replace workers or extract operations to tested Python code.

**Recursive execution**: Workers can call other workers. Critically, workers can autonomously create new workers—the generated definition is saved to disk for user review and approval. Once saved, the new worker is immediately executable. The saved files become artifacts for progressive hardening: review, refine, version control, and gradually extract logic to Python. This makes the system self-scaffolding.

A **worker** = prompt template + configuration + tools, packaged as an executable unit that the LLM interprets.

## Why This Matters

**The LLM context problem**: LLM behavior is context-sensitive. Unlike traditional compilers where unused code is ignored, adding more text to an LLM prompt can degrade results. Large prompts bloat, drift, and fail unpredictably. When you batch everything into a single prompt, the LLM loses focus.

**The solution**: Workers with isolated contexts, connected through three mechanisms:

1. **Worker delegation** (`worker_call`) — Decompose workflows into focused sub-calls. Each worker handles one unit of work (e.g., "evaluate this PDF with this rubric") with its own instructions, model, and tools. No bloated catch-all prompts.

2. **Autonomous worker creation** (`worker_create`) — Workers propose specialized sub-workers when needed. This is same-language metaprogramming: the LLM that executes workers also writes them. Created definitions are saved to disk for review, refinement, and reuse.

3. **Progressive hardening** — Refine created workers over time: edit prompts, add schemas, lock allowlists, extract logic to Python. Orchestrators delegate to vetted workers instead of fragile inline instructions.

**What this enables**:
- **Composability**: Recursive calls feel like function calls, not orchestration glue
- **Autonomy**: Workers identify when they need specialized handlers and create them
- **Control**: Approval gates, security boundaries (sandboxes, tool rules), progressive refinement
- **Reproducibility**: Every sub-call is explicit, loggable, auditable

**Design implications**:
- Optimize for context isolation, not just code reuse
- Worker definitions are the primary boundary for security and side-effects
- Meta-workers (that create other workers) are long-lived components, not scaffolding

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
- **Pre-approved**: Benign operations (read files, call specific workers) execute automatically
- **Approval-required**: Consequential operations (writes, worker creation, external APIs) require explicit user approval
- **Approval context**: User sees full invocation (tool name, arguments, attachments)
- **Session approvals**: Approve once for repeated identical calls

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
5. **Migration** — Extract deterministic operations (scoring, formatting) to tested Python

**Example**:
- **Day 1**: Orchestrator creates `evaluator`, user approves
- **Week 1**: Test runs reveal drift, refine prompt
- **Week 2**: Add structured output schema
- **Week 3**: Extract scoring logic to Python toolbox with tests
- **Week 4**: Worker calls `compute_score()`, math is now deterministic

## Design Principles

1. **Prompts as executables** — Workers are self-contained units you can run from CLI or invoke from other workers

2. **Workers as artifacts** — Saved to disk, version controlled, auditable, refinable by programmers

3. **Security by construction** — Sandboxes, attachment validation, approval enforcement happen in code, not by hoping the LLM follows instructions

4. **Explicit configuration** — Tool access and worker allowlists declared in definitions, not inherited. Model selection follows a predictable chain: worker definition → caller → CLI

5. **Recursive composability** — Workers calling workers should feel like function calls, not orchestration glue

6. **Approval controls** — Balance autonomy with safety. Pre-approve benign operations, require approval for consequential actions. No special cases.

## Architecture

Built on [PydanticAI](https://ai.pydantic.dev/) for agent runtime and structured outputs.

**Core modules** (see [`docs/dependency_injection.md`](dependency_injection.md) for DI architecture):
- `runtime.py` — Worker orchestration, delegation, creation lifecycle
- `protocols.py` — Interface definitions for dependency injection
- `tools.py` — Tool registration (sandboxes, worker_call, worker_create, custom tools)
- `execution.py` — Agent runners and execution context
- `approval.py` — Approval enforcement and session tracking
- `types.py` — Type definitions and data models
- `registry.py` — Worker definition loading and persistence
- `sandbox.py` — Sandboxed filesystem operations

**Key patterns**:
- Protocol-based DI enables recursive worker calls without circular imports
- Security boundaries enforced in code (sandboxes, attachments, approvals)
- Workers as first-class executables with standard invocation: `run_worker(registry, worker, input_data, ...)`

See [`../examples/pitchdeck_eval/`](../examples/pitchdeck_eval/) for a complete multi-worker example.

## Why llm-do vs. Hard-Coded Scripts?

Hard-coding in Python is fine for stable workflows. llm-do provides complementary benefits:

- **Autonomous decomposition** — Workers create specialized sub-workers when needed, no manual scaffolding
- **Context control** — Decompose into focused calls with isolated contexts instead of bloated prompts
- **Iteration speed** — Edit definitions and re-run vs. code → test → deploy
- **Progressive refinement** — Start flexible, harden incrementally, migrate logic to Python when stable
- **Reproducibility** — Every sub-call explicit, loggable, auditable

Workers handle LLM orchestration. Python handles deterministic operations. They complement each other.

## Summary

llm-do treats prompts as executables—packaged with configuration (model, tools, schemas, security) into workers that LLMs interpret.

**Key mechanisms**: Worker delegation (decomposition), worker creation (metaprogramming), progressive hardening (refinement).

**Key primitives**: Sandboxed file access, tool approval system, worker registry, protocol-based DI.
