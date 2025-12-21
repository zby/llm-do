# Worker Delegation: Technical Reference

Technical details for worker-to-worker delegation. For concepts, see [`concept.md`](concept.md). For architecture, see [`architecture.md`](architecture.md).

---

## Tool Signatures

### Worker Tools (LLM-facing)

Each delegated worker appears as a tool with the same name:

```python
def evaluator(
    input: str,
    attachments: list[str] | None = None,
) -> str:
    """Call the evaluator worker to delegate a subtask."""
```

`attachments` parameter is only included when callee's `attachment_policy.max_attachments > 0`.

### ToolContext (Python tools calling workers)

```python
from llm_do import tool_context
from llm_do.types import ToolContext

@tool_context
async def orchestrate(task: str, ctx: ToolContext) -> str:
    return await ctx.call_tool("evaluator", task)
```

---

## Configuration

### Delegation Toolset

```yaml
toolsets:
  delegation:
    evaluator: {}       # Exposes evaluator tool
    summarizer: {}      # Exposes summarizer tool
    worker_create: {}   # Exposes worker_create tool (experimental)
```

Worker tool names share a global namespace. Avoid naming workers `worker_call`, `worker_create`, `shell`, `read_file`, `write_file`, or `list_files`.

---

## Attachment Resolution

When passing `attachments` to a worker tool:

1. Each entry is a file path (relative to CWD or absolute)
2. Delegation toolset expands and resolves each path
3. Validates path exists and is a file
4. Forwards `AttachmentPayload` objects to callee
5. Runtime validates against callee's `attachment_policy` (max count, total bytes, allowed/denied suffixes)

**Note**: `read_file` is for UTF-8 text only. Use attachments for binary files (PDFs, images, spreadsheets).

---

## Model Selection

Model resolution chain (first match wins):

1. CLI `--model` flag (top-level run only)
2. Callee's `model` field in worker definition
3. `LLM_DO_MODEL` environment variable
4. Error if none specified

Nested calls do **not** inherit caller's model. Set `model` per worker or use `LLM_DO_MODEL`.

---

## Nesting Limits

Nested calls capped at `MAX_WORKER_DEPTH` (default 5). Each call increments `WorkerContext.depth`; exceeding limit raises `RecursionError`.

---

## Approval Rules

| Tool | Controls | Payload shown |
|------|----------|---------------|
| Worker tools | Delegating to configured workers | `{input, attachments}` |
| `worker_create` | Creating new worker definitions | `{name, instructions, ...}` |
| `read_file` | Reading files | `{path}` |
| `write_file` | Writing files | `{path}` |

Approval controller modes:
- **`interactive`**: Prompt user for approval
- **`approve_all`**: Auto-approve (testing)
- **`strict`**: Reject all (CI/production)

Session approvals remember identical calls during same run.
