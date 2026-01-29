# Architecture

Internal architecture of llm-do. For theoretical foundation, see [theory.md](theory.md). For API reference, see [reference.md](reference.md).

---

## Agents

An **agent** is an executable prompt artifact: a `.agent` file that defines how to run an LLM-backed task. These files are loaded into `AgentSpec` objects and executed as PydanticAI agents.

```yaml
---
name: main
model: anthropic:claude-haiku-4-5
input_model_ref: schemas.py:PitchInput
toolsets:
  - shell_readonly
  - filesystem_project
  - analyzer      # another agent
---
Instructions for the agent...
```

Agents can call other agents as tools, forming a call tree. Each agent declares its own toolsets - they're not inherited.
Agents can also declare a typed input model via `input_model_ref`; models must subclass `AgentArgs` and implement `prompt_messages()`. Input is provided as a dict (validated into the input model) or as an `AgentArgs` instance.

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
- An agent selected by manifest `entry.agent` (runs as an AgentEntry)
- A Python function selected by manifest `entry.function` (wrapped as a FunctionEntry)

---

## Unified Calling Convention

Theory says: unified calling enables local refactoring when components move across the neural-symbolic boundary. Here's how llm-do implements it.

### The Name Registry

Both agents and tools are registered by name into a shared namespace:

```python
# Agents registered by name (from YAML specs or Python)
runtime.register_agent("sentiment_analyzer", agent_spec)

# Tools registered by name (via toolsets)
@tools.tool
def sentiment_analyzer(text: str) -> dict:
    ...
```

The LLM sees a flat list of callable functions. Whether `sentiment_analyzer` is backed by an agent or Python code is invisible at the call site.

### Why Names Matter

**LLMs output strings.** When an agent decides to call another component, it generates a tool name as text. Name-based dispatch is the only way to resolve that string to an implementation.

**Late binding.** Components can be registered after callers are defined. An agent spec can reference `sentiment_analyzer` before that agent exists—resolution happens at call time.

**Swap without rewiring.** Stabilizing an agent to code means registering a function under the same name. No prompt changes, no call site updates.

### Calling Convention

**From Python (inside a tool):**

```python
# Call by name—works whether target is agent or tool
analysis = await ctx.deps.call_agent("sentiment_analyzer", {"input": text})
```

**From another agent (via LLM tool call):**

The LLM sees both agents and tools as callable functions. It doesn't know—or need to know—which is which.

**Stabilizing doesn't change call sites.** When `sentiment_analyzer` graduates from an agent to a Python function, the LLM still sees a tool named `sentiment_analyzer`. Python orchestration can call the new function directly while agent calls continue to use `ctx.deps.call_agent(...)` as needed.

---

## The Harness Layer

The harness is the orchestration layer sitting on top of the VM. It's imperative—your code owns control flow.

**Key responsibilities:**
- Dispatch calls to agents or tools
- Intercept tool calls for approval
- Manage execution context and depth limits
- Track conversation state within agent runs

**Harness vs. graph DSLs:**

| Aspect | Graph DSLs | llm-do Harness |
|--------|------------|----------------|
| Control flow | DSL constructs | Native Python |
| State | Global context through graph | Local scope per agent |
| Approvals | Checkpoint/resume | Blocking interception |
| Refactoring | Redraw edges | Change code |

Need a fixed sequence? Write a loop. Need dynamic routing? Let the LLM decide. Same calling convention for both.

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

Entry linking resolves toolset specs for agents and produces a single `Entry`
(either AgentEntry or FunctionEntry). Internally, a registry maps agent names to `AgentSpec`
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
Entry executes (`entry.run(...)`)
    │
    ├── Entry code calls runtime.call_agent(...)
    │       → new CallContext (depth+1), same Runtime
    │       → agent runs with its toolsets, returns result
    │
    └── Final output
```

Key points:
- The project manifest (`project.json`) lists which `.agent` and `.py` files to load
- Entry selection is declared in the manifest (`entry.agent` or `entry.function`) and resolves to either
  an agent or a Python function
- Top-level entries (depth 0) keep message history across turns
- Child agent calls get fresh message history (parent only sees tool call/result)
- Run-level settings (approval mode, usage tracking) are shared; toolsets are not
- Max nesting depth prevents infinite recursion (default: 5)
- Entry inputs are normalized to `AgentArgs` (via `input_model`)
- Entry functions are trusted but agent tool calls still go through approval wrappers per run policy

---

## Toolset Instantiation & State

Toolsets are registered as `ToolsetSpec` factories and instantiated per call
to keep state isolated. The runtime calls
optional `cleanup()` hooks when the call scope exits to release handle-based
resources. See [scopes.md](scopes.md) for lifecycle and handle pattern details.

---

## Tool Approval

### Approvals as Syscalls

Every tool call from an LLM can be intercepted. Think syscalls: when an agent needs to do something potentially dangerous, execution blocks until the harness grants permission.

```
Agent run()  ────▶  ApprovalToolset  ────▶  tool execution
                         │
                    (approval check)
```

The LLM decides which tools to call; toolsets are wrapped with `ApprovalToolset` before the agent runs.

### Approval Modes

Tools requiring approval are wrapped by `ApprovalToolset`:
- `--approve-all` bypasses prompts (for automation)
- `--reject-all` denies all approval-required tools
- Interactive mode prompts user, caches session approvals

**Pattern-based rules** auto-approve safe operations:

```python
def my_policy(call_info):
    if call_info.tool_name == "read_file":
        return "approve"  # Always safe
    if call_info.tool_name == "delete_file":
        return "reject"   # Never allow
    return "prompt"       # Ask for others
```

**Approvals reduce risk, not eliminate it.** Prompt injection can trick LLMs into misusing approved tools. Treat approvals as one defense layer. For real isolation, use containers.

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
