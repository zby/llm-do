# Worker Delegation: Technical Reference

This document covers the technical implementation of worker-to-worker delegation in `llm-do`.

For design philosophy and motivation, see [`concept.md`](concept.md). For architecture details, see [`architecture.md`](architecture.md). For examples, see [`../examples/pitchdeck_eval/`](../examples/pitchdeck_eval/).

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
from llm_do import call_worker, WorkerContext

# call_worker requires a caller_context (from parent worker)
# For programmatic use, you'd typically call run_worker instead
result = call_worker(
    registry=worker_registry,
    worker="evaluator",
    input_data={"rubric": "Evaluate this pitch deck thoroughly"},
    caller_context=parent_context,  # Required: WorkerContext from calling worker
    attachments=["input/deck.pdf"],
)
```

## Worker Definition Structure

```yaml
# workers/orchestrator.worker
name: orchestrator
description: Orchestrates multi-step pitch deck evaluation
model: claude-sonnet-4

# Sandbox at top level
sandbox:
  paths:
    input:
      root: ./pipeline
      mode: ro
      suffixes: [".pdf", ".txt"]
      max_file_bytes: 15000000
      read_approval: true  # Require approval to share files as attachments
    output:
      root: ./evaluations
      mode: rw
      write_approval: true  # Writes require approval

# Toolsets as class paths or aliases
toolsets:
  filesystem: {}
  delegation:
    allow_workers:
      - evaluator  # Only allow calling the evaluator worker
---

You coordinate pitch deck evaluations. First list PDFs in the input sandbox,
then process each one using the locked evaluator worker.
Write results to the output sandbox.
```

## Attachment Resolution

When a worker passes `attachments` to `worker_call`, each entry must reference one of the caller's sandboxes (e.g., `attachments=["input/deck.pdf"]`).

The runtime:
1. Resolves the path inside that sandbox
2. Blocks escape attempts (`..` or absolute paths)
3. Re-applies the caller's `attachment_policy` (count, total bytes, suffix allow/deny)
4. Checks `read_approval` for the attachment path (if configured in PathConfig)
5. Forwards validated files to the callee

This keeps delegated attachments confined to data the caller already has permission to access.

### Attachment Approval

Attachments can require user approval before being shared with another worker. Configure via `read_approval` on the sandbox path:

```yaml
sandbox:
  paths:
    documents:
      root: ./docs
      mode: ro
      read_approval: true  # User must approve each attachment
```

When approval is required, the user sees:
- **Path**: Full sandbox-relative path (e.g., `documents/secret.pdf`)
- **Size**: File size in bytes
- **Target worker**: Which worker will receive the file

This allows users to review what data is being shared with delegated workers.

| `read_approval` setting | Behavior |
|------------------------|----------|
| Not configured / false | Attachments shared (auto-approved) |
| `true` | User prompted for each attachment |

**Important**: `read_file` is for UTF-8 text only. Configure `suffixes` on a sandbox path to enumerate safe file types. Binary files (PDF, images, spreadsheets) should go through `attachments`, not `read_file`.

## Model Selection

Worker delegation resolves the model using this chain:

1. The callee's `model` field in its worker definition
2. The caller's effective model (inherited from its caller or CLI)
3. The CLI `--model` flag
4. Error if none specified

**Example**: If you run `llm-do orchestrator --model claude-sonnet-4`, the orchestrator uses `claude-sonnet-4`. Any workers it calls without their own `model` field will also use `claude-sonnet-4` (inherited from the orchestrator).

## Tool Approval System

Tool approval is configured per-path in the sandbox configuration:

```yaml
sandbox:
  paths:
    input:
      root: ./input
      mode: ro
      read_approval: true   # Approve sharing files as attachments

    output:
      root: ./output
      mode: rw
      write_approval: true  # Writes require user approval
```

Worker delegation (`worker.call`) and creation (`worker.create`) always go through the approval controller. The controller's mode determines behavior:

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
| `sandbox.read` | Sharing files as attachments to `worker_call` | `{path, bytes, target_worker}` |
| `sandbox.write` | Writing files via `write_file` | `{path}` |
| `worker.call` | Delegating to another worker | `{worker, attachments}` |
| `worker.create` | Creating new worker definitions | `{name, instructions, ...}` |

**Note**: `sandbox.read` approval is separate from `worker.call` approval. You can pre-approve worker calls but still require approval for each attachment being shared.

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

Worker delegation is implemented in `llm_do/runtime.py`. Key components:

**WorkerRegistry**: Manages loading/saving worker definitions from filesystem

**Sandbox**: Handles file access boundaries, path resolution, and escape prevention

**AttachmentValidator**: Resolves attachment paths and enforces `AttachmentPolicy`

**ApprovalController**: Manages tool approval rules and user callbacks

**call_worker()** orchestrates the full delegation lifecycle:
1. Load callee definition from registry
2. Resolve and validate attachments (via `AttachmentValidator`)
3. Check `sandbox.read` approval for each attachment
4. Compute effective model (callee → caller → CLI)
5. Create WorkerContext with sandbox and approval controller
6. Build PydanticAI agent with tools
7. Execute and return WorkerRunResult

**create_worker()** handles autonomous worker creation:
1. Takes minimal WorkerSpec (name, instructions, description, schema, model)
2. Applies WorkerCreationDefaults to expand to full WorkerDefinition
3. Saves to registry (respects locked flag)
4. Subject to approval via "worker.create" tool rule

From the LLM's point of view, all of this is exposed as `worker_call` and `worker_create` tools. The model only decides which worker to invoke, what input to send, which files to attach, and (for creation) what instructions the new worker should have.
