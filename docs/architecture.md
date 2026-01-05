# Architecture

Internal architecture of llm-do. For high-level concepts, see [`concept.md`](concept.md).

---

## Workers

A **worker** is an executable prompt artifact: a `.worker` file that defines how to run an LLM-backed task.

```yaml
---
name: main
model: anthropic:claude-haiku-4-5
toolsets:
  shell: {}
  filesystem: {}
  analyzer: {}      # another worker
---
Instructions for the worker...
```

Workers can call other workers as tools, forming a call tree. Each worker declares its own toolsets - they're not inherited.

---

## Runtime: Two Scopes

When a worker runs, it operates within two scopes:

**RuntimeConfig** (shared across all workers in a run):
- Approval policy, usage tracking, event callbacks
- Like a web server's global config

**CallFrame** (per-worker):
- Current prompt, message history, nesting depth
- Like a request context - isolated per worker call

This separation means:
- **Shared globally**: Usage tracking, event callbacks, the run-level approval mode (approve-all/reject-all/prompt)
- **Per-worker, no inheritance**: Message history, toolsets, per-tool approval rules

---

## Execution Flow

```
CLI or Python
    │
    ▼
Load .worker file → resolve toolsets
    │
    ▼
run_entry() creates RuntimeConfig + CallFrame
    │
    ▼
Worker builds PydanticAI Agent → runs
    │
    ├── Tool call to another worker?
    │       → new CallFrame (depth+1), same RuntimeConfig
    │       → child runs, returns result
    │
    └── Final output
```

Key points:
- Child workers get fresh message history (parent only sees tool call/result)
- Run-level settings (approval mode, usage tracking) are shared; toolsets are not
- Max nesting depth prevents infinite recursion (default: 5)

---

## Tool Approval

Tools requiring approval are wrapped by `ApprovalToolset`:
- `--approve-all` bypasses prompts (for automation)
- `--reject-all` denies all approval-required tools
- Interactive mode prompts user, caches session approvals

---

## Built-in Toolsets

- **filesystem**: `read_file`, `write_file`, `list_files`
- **shell**: command execution with whitelist-based approval

Python toolsets are discovered from `.py` files. Toolsets can be referenced by alias or full class path.
