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
Workers can also declare a typed input schema via `schema_in_ref`; schemas must subclass `WorkerArgs` and implement `prompt_spec()`. Input can be a string, list (with `Attachment`s), or dict.

---

## Runtime: Shared + Per-Call

When an entry runs (usually a worker), it operates within two scopes owned by a **Runtime**:

**Runtime** (process-scoped, shared across runs in a session):
- Owns a `RuntimeConfig` plus mutable runtime state (usage, message log, approval callback cache)
- Created once per CLI/TUI session or embedding, reused across runs in-process (not persisted beyond the process)

**RuntimeConfig** (immutable policy/config):
- Approval policy, event callbacks, max depth, verbosity
- Like a web server's global config

**CallScope** (per-entry call, may span multiple turns in chat for workers):
- Owns CallFrame + toolset instances for a single entry invocation
- Cleans up toolsets when the scope exits

**CallFrame** (per-entry call state):
- Current prompt, message history, nesting depth, active toolsets
- Like a request context - isolated per call

This separation means:
- **Shared globally**: Usage tracking, event callbacks, the run-level approval mode (approve-all/reject-all/prompt)
- **Per-call, no inheritance**: Message history, active toolsets, per-tool approval rules

Note: `Worker.toolset_specs` are the *declared* toolset factories from configuration. Think of these names as run-scoped capabilities: a stable registry of what a worker is allowed to use. `CallFrame.active_toolsets` are the per-call instances created from those specs at execution time. This makes toolset identity global but toolset state local to the call (see [Trust Boundary](#trust-boundary)).

Implementation layout mirrors the scopes:
- `llm_do/runtime/shared.py`: `Runtime`, `RuntimeConfig`, usage/message sinks
- `llm_do/runtime/call.py`: `CallConfig`, `CallFrame`, `CallScope`
- `llm_do/runtime/deps.py`: `WorkerRuntime`, `ToolsProxy`
- `llm_do/runtime/toolsets.py`: toolset lifecycle helpers

---

## Execution Flow

Entry linking resolves toolset specs and produces a single entry (worker or
`@entry` function). Internally, a registry-like symbol table maps names to
resolved entries during the link step.

```
CLI or Python
    │
    ▼
Build entry (link step resolves toolset specs)
    │
    ▼
Runtime.run_entry() creates CallScope
    │
    ▼
Entry executes (CallScope.run_turn executes each prompt)
    │
    ├── Tool call to another entry?
    │       → new CallScope (depth+1), same Runtime
    │       → child runs, returns result
    │
    └── Final output
```

Key points:
- Entry selection requires exactly one candidate: a worker marked `entry: true`
  or a single `@entry` function.
- Top-level workers (depth 0) keep message history across turns in a CallScope
- Child workers get fresh message history (parent only sees tool call/result)
- Run-level settings (approval mode, usage tracking) are shared; toolsets are not
- Max nesting depth prevents infinite recursion (default: 5)
- EntryFunction inputs are normalized to `WorkerArgs` (via `schema_in`)
- EntryFunction tool calls are trusted but still go through approval wrappers per run policy

---

## Toolset Instantiation & State

Toolsets are registered as `ToolsetSpec` factories and instantiated per call
to keep state isolated. In chat mode, the top-level call scope can span multiple
turns, so toolset instances persist until that scope closes. The runtime calls
optional `cleanup()` hooks when the call scope exits to release handle-based
resources. See [`docs/toolset-state.md`](toolset-state.md)
for the handle pattern and lifecycle details.

---

## Tool Approval

### Trust Boundary

Approval wrapping gates tool calls that require approval, regardless of whether
they were initiated by an LLM or by trusted code. The trust boundary is who
decides to invoke tools; the tool plane remains consistent.

- **Worker** (LLM boundary): The LLM decides which tools to call. Toolsets are wrapped with `ApprovalToolset` before the agent runs. This is where approval prompts happen.

- **EntryFunction** (`@entry` decorated): Developer's Python code decides which tools to call. Tool calls still flow through `ApprovalToolset` and follow the run approval policy.

```
┌─────────────────────────────────────────────────────┐
│  Tool Plane (approval policy + events)              │
│  ┌───────────────┐     ┌───────────────┐           │
│  │ @entry func   │────▶│ ApprovalToolset│──▶ tool  │
│  └───────────────┘     └───────────────┘           │
│  ┌───────────────┐     ┌───────────────┐           │
│  │ Worker.call() │────▶│ ApprovalToolset│──▶ tool  │
│  └───────────────┘     └───────────────┘           │
└─────────────────────────────────────────────────────┘
```

### Approval Modes

Tools requiring approval are wrapped by `ApprovalToolset`:
- `--approve-all` bypasses prompts (for automation)
- `--reject-all` denies all approval-required tools
- Interactive mode prompts user, caches session approvals

---

## Built-in Toolsets

`filesystem_project` is rooted at the project root (manifest directory for CLI runs).

- **filesystem_cwd**: `read_file`, `write_file`, `list_files` (base: CWD)
- **filesystem_cwd_ro**: `read_file`, `list_files` (base: CWD)
- **filesystem_project**: `read_file`, `write_file`, `list_files` (base: project root)
- **filesystem_project_ro**: `read_file`, `list_files` (base: project root)
- **shell_readonly**: read-only shell commands (whitelist)
- **shell_file_ops**: `ls` (pre-approved) + `mv` (approval required)

Python toolsets are discovered from `.py` files as `ToolsetSpec` factories.
Workers reference toolsets by name only.
