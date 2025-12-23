# Architecture Design from Concept

## Context
Translate the system concept in `docs/concept.md` into a concrete architecture sketch that can guide implementation and documentation.

## Findings
The architecture centers on a unified function interface where workers and tools are both callables with identical semantics. A deterministic harness owns orchestration, approvals, and execution guarantees while allowing LLM reasoning to interleave with Python tools.

Proposed components and responsibilities:

- **Runtime Harness**
  - Main entrypoint that executes workers and tools with the same call API.
  - Owns the execution loop for LLM workers: prompt, response parsing, tool dispatch, retries, and output validation.
  - Enforces max depth and timeouts (ex: 5 levels deep) to avoid runaway recursion.
  - Produces trace logs for worker and tool calls with inputs, outputs, and approval outcomes.

- **Unified Function Interface**
  - Common call signature: `call(name, input, ctx) -> output`.
  - Function metadata includes: name, description, input schema, output schema, tools allowed, and risk profile.
  - Supports both Python tools and LLM workers behind the same interface.

- **Worker Definition**
  - Configured by prompt, model, system instructions, tool allowlist, and schema expectations.
  - After setup, a worker behaves like any other tool: it accepts input, receives a context, and returns output.
  - Uses a `WorkerContext` that exposes `call_tool()` and shared utilities (logging, cancellation, approvals).
  - Can call other workers or tools via the unified interface.

- **Tool Definition**
  - Python callables decorated or registered with metadata and schemas.
  - Can call back into workers through `ToolContext` for hybrid flows.
  - Deterministic validation of inputs and outputs before return.

- **Approval System (Syscall Gate)**
  - All tool calls from workers are intercepted by an approval gate.
  - Rules classify operations (read-only, write, network, destructive) and auto-approve safe ones.
  - Interactive approvals are required for risky actions; approvals are recorded in traces.

- **Tool Registry**
  - Central registry for tools with lookup by name and capability metadata.
  - Workers are registered in the same registry and invoked through the same call interface.

- **Tracing and Debugging**
  - Structured logs for calls, approvals, errors, and retries.
  - Optional artifact capture (inputs, outputs, prompts) to drive future hardening.

Execution flow sketch:

1. Caller invokes `call("worker_name", input)`.
2. Harness loads worker definition and creates `WorkerContext`.
3. Worker prompts model; output parsed for tool calls or final result.
4. For each tool call, approval gate runs; if approved, tool is executed.
5. Tool may call workers via `call()`; recursion depth is tracked.
6. Results are validated against schemas and returned to the caller.

Key architecture constraints:

- Deterministic wrapper must be authoritative (approvals, schemas, timeouts).
- Workers are lightweight, focused, and composable; tools stay deterministic.
- Bidirectional refactoring is enabled by shared call semantics and consistent schemas.

## Open Questions
- What is the minimal schema system: JSON Schema, Pydantic models, or custom types?
- How are worker definitions stored (YAML, Python, or registry code)?
- What are the standard approval policy levels and how are they configured per worker?
- What trace format should be stable enough for tooling (JSONL, sqlite, or structured logs)?
- Do we need a standard for retry/backoff behavior per worker/tool?

## Conclusion
(Add when resolved) Decide the concrete module layout and schema system after validating requirements in `docs/architecture.md`.
