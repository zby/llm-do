# What Is a Worker? (Exploratory Notes)

> This is an intentionally short-lived document meant to capture the current
> behavior of workers so we can reason about future redesigns. Expect it to drift
> as soon as implementation changes land.

## Definition

A **worker** is an executable prompt artifact: a persisted configuration that
says *how* to run an LLM-backed task (instructions, tools, sandboxes, models,
outputs) rather than *what code to call*. Execution happens by loading the
artifact and instantiating a PydanticAI `Agent`, but the worker itself is the
artifact, not the agent.

Workers live as YAML/JSON files managed by `WorkerRegistry`. They can be created
by humans or LLMs (via `worker_create`), are version-controllable, and can be
locked to prevent accidental edits.

## Core Components

| Concern | Worker Concept | Implementation Notes |
| --- | --- | --- |
| Artifact schema | `WorkerDefinition`, `WorkerSpec`, `WorkerCreationDefaults` | Define persisted fields + defaults; validation guards suffix lists, attachment policy, etc. |
| Persistence | `WorkerRegistry` | Loads/saves YAML, resolves prompts from `prompts/`, injects sandbox/tool rule names, resolves output schema via callback. |
| Runtime context | `WorkerContext` | Bundles registry handle, sandbox manager, approval controller, creation defaults, attachments, effective model. Provided as `deps` to the agent. |
| Sandbox surface | `SandboxManager`, `SandboxToolset` | Map declarative sandbox config to safe list/read/write operations with suffix + size enforcement. |
| Approval + policy | `ToolRule`, `ApprovalController` | Each tool call is checked against policy; approval-required calls route through callback with session caching. |
| Delegation + creation tools | `_worker_call_tool`, `_worker_create_tool` | Registered as agent tools so LLMs can call other workers or persist new ones while honoring allowlists and approvals. |
| Execution API | `run_worker`, `call_worker`, `create_worker` | Top-level helpers that orchestrate the lifecycle (load → validate attachments → build context → run agent → coerce output). |

## Lifecycle (Happy Path)

1. **Definition**: YAML file describes instructions, sandboxes, tool rules, and
   optionally inline instructions (raw text only) or prompt file references.
2. **Loading**: `WorkerRegistry.load_definition` resolves the file, renders
   templates, hydrates Pydantic models, and throws if invalid.
3. **Invocation**: `run_worker` computes the effective model (definition → caller
   → CLI), validates attachments, builds sandboxes + approvals, and resolves the
   output schema.
4. **Agent wiring**: `_default_agent_runner` instantiates a PydanticAI `Agent`
   using worker instructions, registers built-in tools, and runs synchronously
   with the formatted user input.
5. **Result**: Raw agent output is optionally validated against the resolved
   schema and returned as `WorkerRunResult` with message logs.

## How Workers Differ from PydanticAI Agents

| Worker | PydanticAI Agent |
| --- | --- |
| Persistent artifact with on-disk schema + metadata | In-memory runtime object |
| Encodes sandbox, attachment, approval, delegation policy | No built-in policy surface |
| Has lifecycle hooks (registry, prompt discovery, locking) | Expects caller to manage prompts |
| Can be created/edited by other workers and locked | No persistence semantics |
| Execution returns structured `WorkerRunResult` and audit-friendly metadata | Returns whatever the agent run chooses |

The worker abstraction therefore sits *above* the agent: it packages the rules
and artifacts that make an agent safe and repeatable.

## Current Pain Points / Open Questions

- `base.py` glues artifact definitions, registry, sandbox plumbing, approval
  logic, and runtime orchestration in one module. Breaking this up would clarify
  boundaries and enable alternate runtimes.
- Workers are file-backed; we do not yet have a first-class Python object with
  methods like `.run()` or `.delegate_to()` that could encapsulate behavior.
- Output schema resolution is still stubbed to a pluggable callback; there is no
  repository of schemas or reflection mechanism.
- Tool rule naming is string-based; we may eventually prefer enums or structured
  policies for better validation and discoverability.
- There is no explicit state diagram describing worker creation → locking →
  promotion, which would help with editor/CLI UX.

These gaps drive the upcoming redesign discussion.

