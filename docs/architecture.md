# Architecture

Internal architecture of llm-do. For high-level concepts, see [concept.md](concept.md). For API reference, see [reference.md](reference.md).

---

## Workers

A **worker** is an executable prompt artifact: a `.worker` file that defines how to run an LLM-backed task.

```yaml
---
name: main
model: anthropic:claude-haiku-4-5
schema_in_ref: schemas.py:PitchInput
toolsets:
  - shell_readonly
  - filesystem_project
  - analyzer      # another worker
---
Instructions for the worker...
```

Workers can call other workers as tools, forming a call tree. Each worker declares its own toolsets - they're not inherited.
Workers can also declare a typed input schema via `schema_in_ref`; schemas must subclass `WorkerArgs` and implement `prompt_spec()`. If omitted, the default schema is `WorkerInput`.

---

## Runtime: Shared + Per-Call

When a worker runs, it operates within two scopes owned by a **Runtime**:

**Runtime** (process-scoped, shared across runs in a session):
- Owns a `RuntimeConfig` plus mutable runtime state (usage, message log, approval callback cache)
- Created once per CLI/TUI session or embedding, reused across runs in-process (not persisted beyond the process)

**RuntimeConfig** (immutable policy/config):
- Approval policy, event callbacks, max depth, verbosity
- Like a web server's global config

**CallFrame** (per-worker, per-call):
- Current prompt, message history, nesting depth
- Like a request context - isolated per worker call

This separation means:
- **Shared globally**: Usage tracking, event callbacks, the run-level approval mode (approve-all/reject-all/prompt)
- **Per-worker, no inheritance**: Message history, toolsets, per-tool approval rules

Implementation layout mirrors the scopes:
- `llm_do/runtime/shared.py`: `Runtime`, `RuntimeConfig`, usage/message sinks
- `llm_do/runtime/call.py`: `CallConfig`, `CallFrame`
- `llm_do/runtime/deps.py`: `WorkerRuntime`, `ToolsProxy`

---

## Execution Flow

`InvocableRegistry` is the symbol table for a run: it maps entry names to invocables
(workers and tool-backed entries) after resolution.

```
CLI or Python
    │
    ▼
Build InvocableRegistry → resolve toolsets
    │
    ▼
Runtime.run_entry() creates CallFrame
    │
    ▼
Worker builds PydanticAI Agent → runs
    │
    ├── Tool call to another worker?
    │       → new CallFrame (depth+1), same Runtime
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

- **filesystem_cwd**: `read_file`, `write_file`, `list_files` (base: CWD)
- **filesystem_cwd_ro**: `read_file`, `list_files` (base: CWD)
- **filesystem_project**: `read_file`, `write_file`, `list_files` (base: worker dir)
- **filesystem_project_ro**: `read_file`, `list_files` (base: worker dir)
- **shell_readonly**: read-only shell commands (whitelist)
- **shell_file_ops**: `ls` (pre-approved) + `mv` (approval required)

Python toolsets are discovered from `.py` files. Workers reference toolsets by name only.
