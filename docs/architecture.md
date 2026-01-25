# Architecture

Internal architecture of llm-do. For high-level concepts, see [concept.md](concept.md). For API reference, see [reference.md](reference.md).

---

## Agents

An **agent** is an executable prompt artifact: a `.worker` file that defines how to run an LLM-backed task. These files are loaded into `AgentSpec` objects and executed as PydanticAI agents.

```yaml
---
name: main
model: anthropic:claude-haiku-4-5
schema_in_ref: schemas.py:PitchInput
toolsets:
  - shell_readonly
  - filesystem_project
  - analyzer      # another agent
---
Instructions for the agent...
```

Agents can call other agents as tools, forming a call tree. Each agent declares its own toolsets - they're not inherited.
Agents can also declare a typed input schema via `schema_in_ref`; schemas must subclass `WorkerArgs` and implement `prompt_messages()`. Input can be a string, list (with `Attachment`s), or dict.

---

## Entry Functions

An **entry function** is the root of execution—a Python function that orchestrates agents. Entry functions:

- Receive input and a `CallContext` for dispatching agent calls
- Can only call agents via `call_agent()`—they cannot use tools directly
- Run under `NullModel` with no toolsets (pure orchestration)
- Are trusted code: no approval needed for the entry itself, but called agents' tool use still flows through approval

```
Entry main(input, ctx)
    │
    ├── ctx.call_agent("analyzer", data)  ──▶ Agent runs with toolsets
    │
    ├── ctx.call_agent("formatter", result) ──▶ Agent runs with toolsets
    │
    └── return final_result
```

Entry can be defined as:
- An agent marked `entry: true` (wrapped automatically)
- A Python `EntrySpec` with a `main` function

---

## Runtime: Shared + Per-Call

When an entry runs (usually an agent), it operates within two scopes:

**Runtime** (process-scoped, shared across runs in a session):
- Owns `RuntimeConfig` plus mutable shared state (usage collector, message log, agent registry)
- Created once per CLI/TUI session or embedding, reused across runs in-process (not persisted beyond the process)

**RuntimeConfig** (immutable policy/config):
- Approval policy, event callbacks, max depth, verbosity
- Like a web server's global config

**CallContext** (per-call orchestrator):
- Holds a reference to the shared `Runtime` plus its own `CallFrame`
- Central dispatcher for agent runs and tool execution
- Spawns child contexts with incremented depth for nested agent calls

**CallFrame** (per-call state):
- `CallConfig`: immutable config (depth, model, active toolsets)
- Mutable state: current prompt, message history
- Like a request context - isolated per call

**CallScope** (lifecycle wrapper for agent calls):
- Wraps a `CallContext` + toolset instances for cleanup
- Ensures toolsets are cleaned up when the scope exits

This separation means:
- **Shared globally**: Usage tracking, event callbacks, agent registry, approval mode
- **Per-call, no inheritance**: Message history, active toolsets, nesting depth

Note: `AgentSpec.toolset_specs` are the *declared* toolset factories from configuration. Think of these names as run-scoped capabilities: a stable registry of what an agent is allowed to use. `CallFrame.config.active_toolsets` are the per-call instances created from those specs at execution time. This makes toolset identity global but toolset state local to the call (see [Trust Boundary](#trust-boundary)).

Implementation layout mirrors the scopes:
- `llm_do/runtime/runtime.py`: `Runtime`, `RuntimeConfig`, usage/message sinks
- `llm_do/runtime/context.py`: `CallContext` (per-call orchestrator)
- `llm_do/runtime/call.py`: `CallConfig`, `CallFrame`, `CallScope`

---

## Execution Flow

Entry linking resolves toolset specs for agents and produces a single `EntrySpec`
with a plain `main` function. Internally, a registry maps agent names to `AgentSpec`
instances during the link step.

```
CLI or Python
    │
    ▼
Build entry (link step resolves agent toolset specs)
    │
    ▼
Runtime.run_entry() creates entry runtime (NullModel, no toolsets)
    │
    ▼
Entry executes (entry_spec.main(...))
    │
    ├── Entry code calls runtime.call_agent(...)
    │       → new CallContext (depth+1), same Runtime
    │       → agent runs with its toolsets, returns result
    │
    └── Final output
```

Key points:
- The project manifest (`project.json`) lists which `.worker` and `.py` files to load
- Entry selection requires exactly one agent marked `entry: true` (in a `.worker` file)
  or a single `EntrySpec` (in Python)
- Top-level entries (depth 0) keep message history across turns
- Child agent calls get fresh message history (parent only sees tool call/result)
- Run-level settings (approval mode, usage tracking) are shared; toolsets are not
- Max nesting depth prevents infinite recursion (default: 5)
- EntrySpec inputs are normalized to `WorkerArgs` (via `schema_in`)
- Entry functions are trusted but agent tool calls still go through approval wrappers per run policy

---

## Toolset Instantiation & State

Toolsets are registered as `ToolsetSpec` factories and instantiated per call
to keep state isolated. The runtime calls
optional `cleanup()` hooks when the call scope exits to release handle-based
resources. See [`docs/toolset-state.md`](toolset-state.md)
for the handle pattern and lifecycle details.

---

## Tool Approval

### Trust Boundary

Approval wrapping gates tool calls that require approval. The LLM decides which
tools to call; toolsets are wrapped with `ApprovalToolset` before the agent runs.

```
Agent run()  ────▶  ApprovalToolset  ────▶  tool execution
                         │
                    (approval check)
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
Agents reference toolsets by name only.
