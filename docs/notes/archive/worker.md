# What Is a Worker?

## Definition

A **worker** is an executable prompt artifact: a persisted configuration that
defines *how* to run an LLM-backed task (instructions, tools, sandboxes, models,
outputs) rather than *what code to call*.

Workers live as YAML/JSON files and can be:
- Created by humans or LLMs
- Version-controlled like source code
- Locked to prevent accidental edits
- Composed (workers can call other workers)

## Lifecycle

1. **Definition** - YAML file describes instructions, sandbox boundaries, tool policies
2. **Loading** - Registry resolves prompts, validates configuration
3. **Invocation** - Runtime builds execution context (sandboxes, approvals, tools)
4. **Execution** - PydanticAI agent runs with worker's instructions and constraints
5. **Result** - Structured output with message logs

## Why Workers? (vs PydanticAI Agents)

| Worker | PydanticAI Agent |
| --- | --- |
| Persistent artifact (YAML/JSON) | In-memory runtime object |
| Encodes security policy (sandbox, approvals) | No built-in policy layer |
| LLMs can create/edit workers | No persistence semantics |
| Version-controllable, lockable | Managed by developer code |
| Structured execution results | Returns agent output |

**The worker abstraction sits *above* the agent**: it packages the rules and
artifacts that make an agent safe, repeatable, and composable.

## Architecture

The implementation is split into focused modules:

- **Protocols** - `FileSandbox`, `WorkerCreator`, `WorkerDelegator` define boundaries
- **Sandbox** - Two-layer model: `FileSandbox` (reusable) + `Sandbox` (llm-do extensions with OS enforcement)
- **Shell Tool** - Pattern-based approval rules for subprocess execution
- **Runtime** - Orchestrates execution with dependency injection
- **Tools** - Worker delegation, creation, and file operations

For details on specific subsystems:
- [sandbox.md](../sandbox.md) - Two-layer sandbox design
- [runtime.md](../runtime.md) - Runtime API and execution

