# llm-do: Concept and Design

## Core Idea

**Treat prompts as executables, with LLMs as the interpreter.**

Just like source code is packaged with build configs and dependencies to become executable programs, prompts need to be packaged with configuration (model, tools, schemas, security constraints) to become executable workers.

**Progressive hardening**: Start with flexible prompts that solve problems. Over time, identify operations that should be deterministic (math, formatting, parsing, validation) and extract them from prompts into tested Python code. The prompt stays as the orchestration layer; deterministic operations move to functions.

**Recursive execution**: Workers can call other workers. Critically, workers can autonomously create new workers—the generated definition is saved to disk for user review and approval. Once saved, the new worker is immediately executable. The saved files become artifacts for progressive hardening: review, refine, version control, and gradually extract logic to Python. This makes the system self-scaffolding.

A **worker** = prompt template + configuration + tools, packaged as an executable unit that the LLM interprets.

## Why This Matters

### The Context Bloat Problem

Large workflows with bloated prompts tend to drift and fail unpredictably. When you batch everything into a single prompt, the LLM loses focus and results become inconsistent.

**Solution**: Decompose into focused sub-calls with tightly scoped inputs. Each worker call handles a single unit of work (e.g., "evaluate exactly this PDF with this procedure") rather than trying to process everything at once. This keeps each call grounded and reproducible.

### The Recursive Call Problem

Making workers call other workers needs to be natural and composable. In many frameworks, templates and tools live in separate worlds, forcing awkward workarounds.

**llm-do solves this** by treating workers as first-class executables where recursive invocation is a natural primitive. This enables:
- **Composability**: Common patterns become reusable building blocks vs. bespoke scripts
- **Uniformity**: Sub-calls inherit the same auditing, logging, and security guarantees as top-level invocations
- **Programmer ergonomics**: Clean recursion is easier to reason about than ad-hoc orchestration glue

### The Self-Scaffolding Problem

Most LLM orchestration systems require you to manually write workflow code. But LLMs are good at decomposing tasks—they can identify when a subtask needs specialized handling and what that handler should look like.

**Solution**: Let workers create new workers autonomously, subject to approval controls. The LLM identifies the need, generates the worker definition, and the system manages approval before saving/using it. The saved file becomes the artifact for progressive hardening.

## Key Capabilities

Four primitives enable this:

### 1. Sandboxed File Access
Workers can read/write files through explicitly configured sandboxes:
- Each sandbox has a root directory and access mode (read-only or writable)
- Path escapes (`..` or absolute paths) are blocked by design
- File size limits prevent resource exhaustion
- Multiple sandboxes can be exposed to different parts of the workflow

**Motivation**: Security by construction. Prevent sandbox escapes and resource bombs through toolbox design, not by hoping the LLM follows instructions.

### 2. Worker-to-Worker Delegation
Workers can invoke other workers with controlled inputs:
- Allowlists restrict which workers can be called
- Attachment validation (count, size, file extensions) happens before execution
- Model inheritance follows a clear chain: worker definition → caller's model → CLI model → error
- Tool access and allowlists are NOT inherited (each worker declares its own)
- Results can be structured (validated JSON) or freeform text

**Motivation**: Enable the two-step pattern (choose → act) and multi-stage workflows. Each worker has tight, focused context. Refining one worker doesn't require touching others.

**Concrete benefits**:
- **Tight context**: Each sub-call scoped to single unit of work, not batching into bloated prompt
- **Guardrails by construction**: File size caps, suffix restrictions, locks enforced in code, not by hoping LLM respects instructions
- **Reproducibility**: Sub-calls are explicit, loggable, re-runnable, auditable—you can trace exactly which worker processed which files with which parameters
- **Iteration speed**: Refine one worker without touching others, they evolve independently

### 3. Tool Call Approval System
Sophisticated control over which tools can be invoked without user intervention:
- **Pre-approved tools**: Benign operations (read files, call specific workers) execute automatically
- **Human-in-the-loop approval**: Potentially dangerous operations (write files, create workers, call arbitrary external APIs) require explicit user approval before execution
- **Configurable policies**: Workers can specify which tools require approval, with sensible defaults
- **Approval context**: User sees the full tool invocation (arguments, context) and can approve, reject, or modify

**Motivation**: Balance autonomy with control. Let workers operate efficiently for safe operations while ensuring humans stay in the loop for consequential actions. This is critical for trust and safety.

### 4. Autonomous Worker Creation
Workers can create specialized sub-workers when they identify the need:
- Worker calls `create_worker(...)` with prompt, schema, and tool config
- Subject to tool approval policy (typically requires human approval)
- User reviews the proposed definition, can edit or reject before saving
- Created workers start with minimal permissions (principle of least privilege)
- Saved definition is immediately executable

**Motivation**: Autonomous task decomposition with human-in-the-loop control. Worker creation is just one instance of the general tool approval system—no special case needed.

## Progressive Hardening

The workflow for evolving a worker from prototype to production:

1. **Autonomous creation**: Worker creates specialized sub-worker, user approves saved definition
2. **Testing**: Run tasks using the created worker, observe behavior
3. **Iteration**: Edit the saved definition—refine prompts, add schemas, tune models
4. **Locking**: Pin orchestrators to vetted worker definitions via allowlists
5. **Migration**: Extract operations that should be deterministic (scoring math, formatting) from prompts into tested Python functions

**Example progression:**
- **Day 1**: Orchestrator creates `evaluator` worker, user approves
- **Week 1**: Test runs reveal inconsistencies, user refines prompt
- **Week 2**: Add structured output schema for validation
- **Week 3**: Extract scoring logic to Python toolbox with tests
- **Week 4**: Worker calls `compute_score()`, math is stable

Workers stay as the orchestration layer; Python handles deterministic operations.

## Design Principles

1. **Prompts as executables**: Workers are self-contained units (prompt + config + tools) you can run from CLI or invoke from other workers

2. **Workers as artifacts**: Generated workers are saved to disk, version controlled, auditable, refinable by programmers

3. **Security by construction**: Sandbox escapes, file size bombs, arbitrary code execution prevented by toolbox design, not LLM instruction-following. Created workers start with minimal permissions.

4. **Explicit configuration**: Tool access and worker allowlists declared in definitions, not inherited. Model selection uses a well-defined fallback chain (worker definition → caller → CLI) for convenience while remaining predictable

5. **Recursive composability**: Workers calling workers should feel like function calls, not template loading gymnastics. The architecture should make this natural.

6. **Sophisticated approval controls**: Balance autonomy with safety through configurable tool approval policies. Pre-approve benign operations, require human approval for consequential actions. Worker creation, file writes, and external API calls are subject to approval, not special-cased.

## Architecture

llm-do provides a complete runtime for worker execution built on PydanticAI:

1. **Workers as first-class executables**
   - Worker = template + config + tools as a loadable, runnable unit
   - Standard invocation interface: `run_worker(registry, worker, input_data, ...)`
   - Tools access the worker registry naturally through `WorkerContext`

2. **Built-in delegation primitives**
   - `worker_call` tool is part of the core runtime
   - Worker loading, validation, and execution happen transparently
   - Recursive calls feel like function calls

3. **Integrated tool approval system**
   - Configurable policies for which tools require human approval
   - Pre-approved tools (reads, specific worker calls) execute automatically
   - Approval-required tools (writes, worker creation, external APIs) prompt user with full context
   - User can approve, reject, or approve for session
   - Sensible defaults with ability to customize per worker or per tool

4. **Worker creation as a first-class capability**
   - Workers can propose new definitions when they identify the need
   - Subject to tool approval policies (no special case)
   - User reviews proposed definition, can edit or reject before saving
   - Created workers start with safe defaults (minimal permissions)
   - Approved definitions are immediately runnable and refinable

5. **Security by construction**
   - Sandboxed file access with escape prevention
   - Attachment validation (size, count, suffix)
   - Worker allowlists and locks
   - No inline code execution
   - Explicit permission grants for created workers

## Example: Pitch Deck Evaluation

**Scenario**: Evaluate multiple pitch decks using a shared rubric.

**Flow**:
1. Orchestrator worker lists PDFs in a directory
2. For each PDF:
   - Calls locked evaluator worker
   - Passes PDF + evaluation rubric
   - Gets back structured JSON (scores, summary, red flags)
   - Writes formatted report to output directory

**What makes this work**:
- **Sandboxed files**: Read-only pipeline directory, writable output directory
- **Worker delegation**: Orchestrator invokes locked evaluator worker per PDF
- **Tight context**: Each evaluator call processes one file with one rubric
- **Progressive hardening**: Start with generated evaluator, refine prompt, extract scoring math to Python

Each PDF gets isolated worker invocation = reproducible results, testable components.

## Why llm-do vs. Hard-Coded Scripts?

Hard-coding in Python is fine for stable workflows. llm-do provides complementary benefits:

- **Autonomous decomposition**: Workers identify when they need specialized sub-workers and create them—no manual scaffolding
- **Balanced control**: Tool approval system lets workers operate efficiently for safe operations while keeping humans in the loop for consequential actions
- **Iteration speed**: Edit worker definitions → re-run, vs. code → test → deploy
- **Composability**: Recursive worker calls via `worker_call` make complex workflows into building blocks
- **Progressive refinement**: Start with generated definition, harden incrementally, migrate logic to Python when stable
- **Reproducibility**: Every sub-call is explicit, loggable, auditable—you can trace exactly what happened

Workers provide the right abstraction for LLM orchestration. Python handles deterministic operations. Workers can scaffold specialized sub-workers when needed, subject to approval controls.

## Summary

**Core concept**: Treat prompts as executables. Package prompts with configuration (model, tools, schemas, security constraints) to create workers that LLMs interpret.

**Key problems solved**:
1. **Context bloat**: Decompose workflows into focused sub-calls instead of bloated single prompts
2. **Recursive calls**: Make workers calling workers a natural primitive
3. **Self-scaffolding**: Let workers autonomously create specialized sub-workers
4. **Safety**: Balance autonomy with control through sophisticated tool approval

**Architecture features**:
- Workers as self-contained definitions (YAML + prompts)
- Sophisticated tool approval system (pre-approved vs. human-in-the-loop)
- Worker creation as one instance of the general approval mechanism
- Sandboxed file access with escape prevention
- Worker delegation with allowlists/locks and attachment validation
- Progressive hardening: creation → approval → test → refine → migrate to Python
- Security by construction: minimal permissions by default, guardrails enforced by code
- Built on PydanticAI for agent runtime and structured outputs

**Benefits delivered**:
- Worker invocation as a natural primitive through `worker_call` tool
- Tool approval system integrated into the core runtime (`ApprovalController`)
- Worker registry part of the core runtime, accessible to all tools via `WorkerContext`
- Approval UX: show full context, approve/reject/approve-for-session
- Tight context per call, guardrails by construction, reproducibility, independent evolution
