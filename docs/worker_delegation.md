# Worker Delegation: Technical Reference

This document covers the technical implementation of worker-to-worker delegation in `llm-do`.

For design philosophy and motivation, see [`concept.md`](concept.md). For architecture details, see [`architecture.md`](architecture.md). For examples, see [`../examples/pitchdeck_eval/`](../examples/pitchdeck_eval/).

## Programmer vs LLM Perspective

**Programmers** work with `WorkerDefinition` YAML files and the Python runtime. Their mental model is "workers are executable units that can safely call other workers" with:
- Delegation tool config to control which worker tools are exposed
- Attachment validation (count, size, suffix) enforced before execution
- Filesystem toolset for file I/O (no path sandboxing; use a container boundary)
- Structured outputs via `output_schema_ref`
- Model resolution per worker (CLI model > worker model > env var)
- Tool approval system for gated operations

**LLMs** see `_worker_*` tools (one per configured worker), plus `worker_create`
and optional `worker_call` if enabled. The model chooses which worker tool to call,
provides input data and attachments, and receives structured or freeform results.
The callee's instructions, model, and tools are defined in its worker definition;
the caller only passes arguments.

## API Signatures

### LLM-Facing Tools

```python
# Conceptual view of the tool the LLM sees
def _worker_evaluator(
    input: str,
    attachments: list[str] | None = None,
) -> str:
    """
    Call the evaluator worker to delegate a subtask.

    The worker will process the input with its own instructions and tools.
    Results may be structured JSON or freeform text depending on the worker's
    output_schema_ref configuration.
    """
```

`attachments` is only included when the callee's `attachment_policy.max_attachments > 0`.

```python
@agent.tool
def worker_create(
    name: str,
    instructions: str,
    description: str,
    output_schema_ref: str | None = None,
    model: str | None = None,
) -> dict:
    """
    Create a new worker definition with specialized instructions.

    The worker will be saved to the registry with safe defaults (minimal
    toolsets and attachment policy). Subject to user approval.
    """
```

### Programmer-Facing API

```python
import asyncio

from llm_do import call_worker_async, WorkerContext

# call_worker_async requires a caller_context (from parent worker)
result = asyncio.run(call_worker_async(
    registry=worker_registry,
    worker="evaluator",
    input_data={"rubric": "Evaluate this pitch deck thoroughly"},
    caller_context=parent_context,  # Required: WorkerContext from calling worker
    attachments=["input/deck.pdf"],
))
```

### ToolContext for Nested Calls

Tools can call workers directly via `ToolContext`. This enables hybrid tools—Python functions that handle deterministic logic but delegate fuzzy parts to focused workers. See [`concept.md`](concept.md#the-hybrid-pattern) for the pattern and use cases.

```python
from pydantic_ai import RunContext
from llm_do.types import ToolContext

@agent.tool
async def orchestrate(ctx: RunContext[ToolContext], task: str) -> str:
    return await ctx.deps.call_worker("evaluator", task)
```

## Worker Definition Structure

```yaml
# orchestrator.worker (at project root)
name: orchestrator
description: Orchestrates multi-step pitch deck evaluation
model: anthropic:claude-sonnet-4

toolsets:
  filesystem:
    read_approval: false
    write_approval: true
  delegation:
    evaluator: {}       # Exposes _worker_evaluator tool
    worker_create: {}   # Exposes worker_create tool
---

You coordinate pitch deck evaluations. First list PDFs in input/,
then process each one using the evaluator worker via _worker_evaluator.
Write results to evaluations/.
```

Note: the evaluator worker should declare its own `attachment_policy` (for
example, allow `.pdf`) to accept attachments.

## Attachment Resolution

When a worker passes `attachments` to a delegation tool (`_worker_*`), each entry
is a file path (relative to CWD or absolute).

The delegation toolset:
1. Expands and resolves each path
2. Ensures the path exists and is a file
3. Forwards `AttachmentPayload` objects to the callee

The runtime then validates attachments against the callee's `attachment_policy`
(max count, total bytes, allowed/denied suffixes). There is no path sandboxing.

**Important**: `read_file` is for UTF-8 text only. Use attachments for binary
files (PDFs, images, spreadsheets).

## Model Selection

Worker delegation resolves the model using this chain:

1. CLI `--model` flag (top-level run only)
2. The callee's `model` field in its worker definition
3. `LLM_DO_MODEL` environment variable
4. Error if none specified

Nested worker calls do not inherit the caller's model; set `model` per worker
or rely on `LLM_DO_MODEL`.

## Nesting Limits

Nested worker calls are capped at `MAX_WORKER_DEPTH` (default 5). Each nested
call increments `WorkerContext.depth`; exceeding the limit raises `RecursionError`.

## Tool Approval System

Tool approval is configured per toolset (filesystem, shell, delegation, custom):

```yaml
toolsets:
  filesystem:
    read_approval: true
    write_approval: true
  delegation:
    evaluator: {}
    worker_create: {}
```

Worker delegation (`_worker_*`/`worker_call`) and creation (`worker_create`) always go through the approval controller. The controller's mode determines behavior:

- **`approve_all`**: Auto-approve all requests (testing, non-interactive)
- **`interactive`**: Prompt user for approval
- **`strict`**: Reject all approval-required operations (production, CI)

When approval is required, the user sees:
- Which tool is being invoked
- The full arguments
- Context about why

They can then approve, reject, or modify before execution. Session approvals remember approvals for identical calls during the same run.

### Approval Rules Reference

| Rule | Controls | Payload shown to user |
|------|----------|----------------------|
| `read_file` | Reading files via filesystem toolset | `{path}` |
| `write_file` | Writing files via filesystem toolset | `{path}` |
| `_worker_*` | Delegating to another worker | `{worker, attachments}` |
| `worker_call` | Delegating to another worker by name | `{worker, attachments}` |
| `worker_create` | Creating new worker definitions | `{name, instructions, ...}` |

## Autonomous Worker Creation

The created worker inherits `WorkerCreationDefaults` from the runtime:
- Default model (if configured)
- Default toolsets (if any)
- Default attachment policy
- Always starts with `locked: false`

Workflow:
1. Orchestrator identifies need for specialized subtask
2. Calls `worker_create(...)` with appropriate instructions
3. User reviews proposed definition (sees full YAML)
4. User can approve, edit, or reject
5. If approved, worker is immediately available for use

## Implementation Architecture

Worker delegation is implemented in `llm_do/runtime.py` with tool support in
`llm_do/delegation_toolset.py`. Key components:

**WorkerRegistry**: Manages loading/saving worker definitions from filesystem

**DelegationToolset**: Exposes `_worker_*` tools and resolves attachment paths

**AttachmentPolicy**: Enforces count/size/suffix limits for inbound attachments

**ApprovalController**: Manages tool approval rules and user callbacks

**call_worker_async()** orchestrates the full delegation lifecycle:
1. Load callee definition from registry
2. Check max worker depth (recursion protection)
3. Validate attachments against the callee's `attachment_policy`
4. Resolve model (CLI > worker > env)
5. Create WorkerContext with approval controller and attachments
6. Build PydanticAI agent with tools
7. Execute and return WorkerRunResult

**create_worker()** handles autonomous worker creation:
1. Takes minimal WorkerSpec (name, instructions, description, schema, model)
2. Applies WorkerCreationDefaults to expand to full WorkerDefinition
3. Saves to registry (respects locked flag)
4. Subject to approval via `worker_create`

From the LLM's point of view, all of this is exposed as `_worker_*` tools (one per configured worker) and `worker_create`. The model only decides which worker to invoke, what input to send, which files to attach, and (for creation) what instructions the new worker should have.
