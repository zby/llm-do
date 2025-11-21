# PydanticAI rewrite: llm-do architecture assessment and proposal

This document reviews the proposed PydanticAI + Jinja architecture for `llm-do`, checks how it supports the project’s core use cases, and rewrites the design into a structured plan we can implement.

## Alignment with llm-do use cases

| Capability | Status | Notes |
| --- | --- | --- |
| Sandboxed file access | ✅ Supported via `SandboxManager` enforcing roots, modes, suffix and size caps. Approval wrapper can gate writes. |
| Worker-to-worker delegation | ✅ Built-in through a `call_worker` tool that respects allowlists and model inheritance. |
| Tool approval / human-in-the-loop | ✅ Uses `ApprovalRequiredToolset` to defer calls; host can resume with `DeferredToolResults`. |
| Autonomous worker creation | ✅ `create_worker(spec)` gives the LLM a single-parameter flow; profiles apply policies. |
| Progressive hardening | ✅ File-backed workers, schemas, allowlists, and locks create the artifact surface for iteration. |
| CLI/host ergonomics | ✅ `run_worker` offers a single entry point with history/deferred support. |
| Security defaults | ⚠️ Good foundations, but attachment validation and sandbox total-size accounting need explicit hooks. |
| Output schema resolution | ⚠️ Assumes `resolve_output_type` exists; we should define discovery rules (registry, module imports). |
| Locking/versioning | ⚠️ `locked` is present but its enforcement rules (e.g., block edits, restrict toolset) should be spelled out. |
| Model selection | ✅ Clear inheritance rule (worker → caller → CLI). |

Overall, the sketch covers llm-do’s core scenarios (recursive execution, approval flows, self-scaffolding) with minimal Python overhead for worker authors. Remaining gaps are small policy clarifications: attachment enforcement, lock semantics, and schema resolution.

## Proposed architecture (rewritten)

### Worker artifacts

Workers live as file-backed artifacts, editable without Python:

- **`WorkerDefinition` (YAML/JSON):** name, description, instructions (Jinja/plain), optional `model`, optional `output_schema_ref`, sandbox configs, attachment policy, worker allowlist, tool rules, `locked` flag.
- **`WorkerSpec` (LLM-facing):** minimal single-argument schema (`name`, `instructions`, optional `output_schema_ref`, optional `kind`) used by `create_worker`.
- **`WorkerCreationProfile` (Python config):** default sandboxes, attachment policy, tool rules, allowlist, and optional default model applied when expanding a `WorkerSpec` into a persisted definition.

Creation flow: LLM proposes a `WorkerSpec` → approval → runtime expands with the active `WorkerCreationProfile` → `WorkerDefinition` saved to disk.

### Runtime context and model inheritance

`WorkerContext` is shared across tools during a run. It holds the current worker definition, registry handle, sandbox manager, creation profile, effective model, run ID, attachments, and clock.

Effective model selection follows a simple rule:

```
worker.model → caller.effective_model → CLI-provided model
```

Top-level runs use `cli_model` unless the worker pins a model. Delegated calls inherit the caller’s effective model when the callee leaves `model` unset.

### Registry and execution API

- **`WorkerRegistry`**: resolves file paths, loads/saves definitions, and resolves output schemas. Construction is light; policies live in toolsets/profiles.
- **`run_worker`**: single entry point for hosts/CLI. Steps:
  1. Load definition and compute `effective_model`.
  2. Resolve output schema into a Pydantic model (or `DeferredToolRequests`).
  3. Build an `Agent` with instructions and the worker toolset.
  4. Execute with `WorkerContext`, optional history, attachments, and deferred results.
  5. Return `WorkerRunResult` containing output, any deferred tool requests, and usage accounting.

Hosts can surface deferred tools for approval and resume runs with preserved message history and approvals.

### Toolsets

**Sandboxed filesystem**
- `SandboxManager` enforces root scoping, RO/RW modes, suffix/size limits, and (to be added) total-size accounting.
- `sandbox_read` and `sandbox_write` are exposed through a `FunctionToolset`. Writes are typically approval-gated.
- **PydanticAI built-in to reuse:** the library ships a `pydantic_ai.tools.filesystem` helper with `read_text`, `write_text`, and directory listing helpers. When available, wrap it with sandbox-aware path resolution (or plug sandbox roots into its `base_dir` argument) to reduce custom code while still enforcing suffix/size limits.

**Worker delegation**
- `call_worker(worker, input)` verifies allowlists, builds a sub-agent with inherited model and toolset, and returns typed results. Usage accounting can be aggregated via the shared context.

**Worker creation**
- `create_worker(spec)` expands a `WorkerSpec` using the active profile, defaults `model=None` to allow inheritance, and saves the definition. Usually marked `approval_required`.

**Approval wrapper**
- `build_worker_toolset` combines the base toolsets and applies per-worker `ToolRule` policies using `ApprovalRequiredToolset`, turning selected calls into deferred requests for human review.

### Attachments and locking (clarifications)

- **Attachments:** enforce `AttachmentPolicy` on inbound files before execution (count, total bytes, suffix). Share vetted attachments with delegated workers; document whether sub-workers can add more.
- **Locking:** when `locked=True`, block `save_definition` unless explicitly forced and optionally restrict high-risk tools (e.g., creation, writes) regardless of tool rules.

### Progressive hardening path

1. **Prototype:** no `output_schema_ref`, broad approvals (writes gated), rapid iteration on YAML definitions.
2. **Structure:** add Pydantic schemas, let the runtime validate and auto-retry formatting failures.
3. **Extract logic:** move deterministic steps into tools (e.g., `compute_score`, filename normalization) with tests.
4. **Lock and version:** pin trusted workers via `locked=True`, narrow allowlists/tool rules, version definitions (`foo.v3.yaml`).

### Example: pitch deck evaluation

- **`pitch_orchestrator`**: orchestrates listing PDFs, calls `pitch_evaluator` per deck, writes reports. Sandboxes: `input` (ro), `output` (rw). Tool rules: reads auto; writes approval/auto per environment; `call_worker` allowed only for `pitch_evaluator`.
- **`pitch_evaluator`**: reads a single deck, returns `PitchScore` schema. Sandboxes: `input` (ro); tool rules: read-only.

Flow: host runs orchestrator → delegation handles per-deck evaluation with model inheritance → writes go through approval as configured → rerun with approvals if deferred.

## Next steps

- Define concrete `resolve_output_type` rules (module registry, dotted-path import) and error reporting.
- Implement attachment validation in the registry/runner pipeline.
- Decide enforcement semantics for `locked` workers and document override mechanisms.
- Wire aggregated usage accounting through delegation.
