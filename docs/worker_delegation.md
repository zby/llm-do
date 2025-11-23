# Worker Delegation: Technical Reference

This document covers the technical implementation of worker-to-worker delegation in `llm-do`.

For design philosophy and motivation, see [`concept_spec.md`](concept_spec.md). For examples, see [`../examples/pitchdeck_eval/`](../examples/pitchdeck_eval/).

## Programmer vs LLM Perspective

**Programmers** work with `WorkerDefinition` YAML files and the Python runtime. Their mental model is "workers are executable units that can safely call other workers" with:
- Worker allowlists to restrict which workers can be called
- Attachment validation (count, size, suffix) enforced before execution
- Sandboxed file access for security
- Structured outputs via `output_schema_ref`
- Model inheritance chain: worker definition → caller → CLI
- Tool approval system for gated operations

**LLMs** see tools like `worker_call` and `worker_create` that mean "delegate to another worker" and "create a new specialized worker." The model chooses which worker to call, provides input data and attachments, and receives structured or freeform results. The callee's instructions, model, and tools are defined in its worker definition; the caller only passes arguments.

## API Signatures

### LLM-Facing Tools

```python
# Conceptual view of the tool the LLM sees
@agent.tool
def worker_call(
    worker_name: str,
    input_data: dict | str,
    attachments: list[str] | None = None,
) -> WorkerRunResult:
    """
    Call another registered worker to delegate a subtask.

    The worker will process the input with its own instructions and tools.
    Results may be structured JSON or freeform text depending on the worker's
    output_schema_ref configuration.
    """
```

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
    permissions, no sandboxes, no tool access). Subject to user approval.
    """
```

### Programmer-Facing API

```python
from llm_do.pydanticai import call_worker

result = call_worker(
    worker_name="evaluator",
    input_data={"rubric": "Evaluate this pitch deck thoroughly"},
    attachments=["input/deck.pdf"],
    model="claude-sonnet-4",  # Optional override
    registry=worker_registry,
    approval_callback=approve_all_callback,
)
```

## Worker Definition Structure

```yaml
# workers/orchestrator.yaml
name: orchestrator
description: Orchestrates multi-step pitch deck evaluation
instructions: |
  You coordinate pitch deck evaluations. First list PDFs in the input sandbox,
  then process each one using the locked evaluator worker.
  Write results to the output sandbox.

model: claude-sonnet-4
allow_workers:
  - evaluator  # Only allow calling the evaluator worker

sandboxes:
  input:
    path: ./pipeline
    mode: ro
    allowed_suffixes: [".pdf", ".txt"]
    max_bytes: 15000000
  output:
    path: ./evaluations
    mode: rw

tool_rules:
  - name: sandbox.write
    allowed: true
    approval_required: true  # Writes require approval
  - name: worker.call
    allowed: true
    approval_required: false  # Pre-approved for allowed workers
```

## Attachment Resolution

When a worker passes `attachments` to `worker_call`, each entry must reference one of the caller's sandboxes (e.g., `attachments=["input/deck.pdf"]`).

The runtime:
1. Resolves the path inside that sandbox
2. Blocks escape attempts (`..` or absolute paths)
3. Re-applies the caller's `attachment_policy` (count, total bytes, suffix allow/deny)
4. Forwards validated files to the callee

This keeps delegated attachments confined to data the caller already has permission to access.

**Important**: `sandbox_read_text` is for UTF-8 text only. Configure `text_suffixes` on a sandbox to enumerate safe file types. Binary files (PDF, images, spreadsheets) should go through `attachments`, not `sandbox_read_text`. Combine with `attachment_suffixes` to restrict which binaries can be shared with sub-workers.

## Model Selection

Worker delegation resolves the model using this chain:

1. The callee's `model` field in its worker definition
2. The caller's effective model (inherited from its caller or CLI)
3. The CLI `--model` flag
4. Error if none specified

**Example**: If you run `llm-do orchestrator --model claude-sonnet-4`, the orchestrator uses `claude-sonnet-4`. Any workers it calls without their own `model` field will also use `claude-sonnet-4` (inherited from the orchestrator).

## Tool Approval System

Each worker configures which tools require approval via `tool_rules`:

```yaml
tool_rules:
  - name: sandbox.read
    allowed: true
    approval_required: false  # Reads are pre-approved

  - name: sandbox.write
    allowed: true
    approval_required: true  # Writes require user approval

  - name: worker.call
    allowed: true
    approval_required: false  # Delegation pre-approved (if in allowlist)

  - name: worker.create
    allowed: true
    approval_required: true  # Creating workers requires approval
```

When a tool with `approval_required: true` is called, the runtime gates it through an approval callback. The user sees:
- Which tool is being invoked
- The full arguments
- Context about why

They can then approve, reject, or modify before execution. Session approvals remember approvals for identical calls during the same run.

When `worker_call` sends attachments, the approval payload includes each sandbox-relative path and file size so the operator understands exactly which files will be shared with the delegated worker.

## Autonomous Worker Creation

The created worker inherits `WorkerCreationDefaults` from the runtime:
- Default sandboxes (if any)
- Default tool rules (safe defaults: reads pre-approved, writes approval-required)
- Default attachment policy
- Always starts with `locked: false`

Workflow:
1. Orchestrator identifies need for specialized subtask
2. Calls `worker_create(...)` with appropriate instructions
3. User reviews proposed definition (sees full YAML)
4. User can approve, edit, or reject
5. If approved, worker is immediately available for use

## Implementation Architecture

Worker delegation is implemented in `llm_do/pydanticai/base.py`. Key components:

**WorkerRegistry**: Manages loading/saving worker definitions from filesystem

**SandboxManager**: Handles path resolution, escape prevention, and file validation

**ApprovalController**: Manages tool approval rules and user callbacks

**call_worker()** orchestrates the full delegation lifecycle:
1. Load callee definition from registry
2. Validate attachments against policy
3. Compute effective model (callee → caller → CLI)
4. Create WorkerContext with sandboxes and approval controller
5. Build PydanticAI agent with tools
6. Execute and return WorkerRunResult

**create_worker()** handles autonomous worker creation:
1. Takes minimal WorkerSpec (name, instructions, description, schema, model)
2. Applies WorkerCreationDefaults to expand to full WorkerDefinition
3. Saves to registry (respects locked flag)
4. Subject to approval via "worker.create" tool rule

From the LLM's point of view, all of this is exposed as `worker_call` and `worker_create` tools. The model only decides which worker to invoke, what input to send, which files to attach, and (for creation) what instructions the new worker should have.
