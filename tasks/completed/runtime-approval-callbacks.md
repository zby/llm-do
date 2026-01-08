# Runtime-Scoped Approval Callbacks

## Status
completed

## Prerequisites
- [x] none

## Goal
Introduce a non-entry-bound runtime that owns approval callback creation, encapsulates runtime-wide policy, and can run any entry while reusing a global `RuntimeConfig`.

## Context
- Relevant files/symbols: `llm_do/runtime/context.py` (`RuntimeConfig`, `CallFrame`, `WorkerRuntime`), `llm_do/runtime/approval.py`, `llm_do/runtime/runner.py`, `llm_do/cli/main.py`, `experiments/inv/v2_direct/run.py`, `docs/reference.md`, `docs/architecture.md`
- Related tasks/notes/docs: `docs/notes/execution-mode-scripting-simplification.md`
- How to verify / reproduce: `uv run ruff check .`, `uv run mypy llm_do`, `uv run pytest`

## Decision Record
- Decision: introduce a non-entry-bound `Runtime` object
- Motivation:
  - Python embedding currently duplicates CLI wiring (approval policies, display backends, verbosity, model override).
  - Approval callback creation happens in CLI code, making non-CLI usage feel second-class.
  - Global run policy (`RuntimeConfig`) exists, but we lack a single runtime surface to own it and expose a consistent API.
  - A non-entry `Runtime` makes it explicit that workers are run within a shared execution environment rather than “like pure functions.”
- Inputs: CLI currently builds approval callback/policy; runtime already owns run policy fields; need shared session caching for approvals; `RuntimeConfig` remains the immutable policy container; `WorkerRuntime` should own `Runtime` + `CallFrame` (not config)
- Options:
  - Keep policy-only in runtime and resolve per run
  - Resolve callback once at runtime creation and reuse
  - Introduce a new `Runtime` facade that owns a `RuntimeConfig` instance and constructs per-entry `CallFrame`
- Outcome:
  - Name: `Runtime` (conveys global execution environment; mirrors CLI semantics)
  - Relationship: `Runtime` owns `RuntimeConfig`, constructs `CallFrame` per run, and uses a fresh `WorkerRuntime` per entry call (avoids shared mutable frames and preserves per-entry message history)
  - Config/state split: `RuntimeConfig` stays deeply immutable; runtime-scoped mutable state (usage, message log, approval callback cache) lives on `Runtime`
  - Runtime wiring: `WorkerRuntime` holds a `Runtime` reference instead of `RuntimeConfig` (can still expose `.config` as a property)
  - Approval lifecycle: resolve approval callback once at `Runtime` creation; cache is runtime-scoped (enables session-level caching and avoids re-wrapping)
  - Model: store `cli_model` on `Runtime` and pass it to model selection on each run (consistent CLI override, no per-call wiring)
  - UI: `Runtime` owns output formatting/event handling configuration (centralizes headless/CLI-like formatting, reduces embedding boilerplate)
  - Accumulator API: keep it simple for now with `runtime.usage` and `runtime.message_log`; `message_log` is a list of `(worker_id, messages)` tuples (no tree yet)
  - Runtime API proposal:
    - `Runtime.__init__(*, cli_model=None, run_approval_policy, max_depth=5, on_event=None, verbosity=0)`
    - `Runtime.run_invocable(invocable, prompt, *, model=None, message_history=None) -> (result, worker_runtime)`
    - `Runtime.usage` / `Runtime.message_log` accessors
- Follow-ups:
  - Consider future structure for accumulator trees if needed

## Tasks
- [x] Define `Runtime` constructor parameters and public methods
- [x] Implement `Runtime` to own `RuntimeConfig` and construct `WorkerRuntime` + `CallFrame` per run
- [x] Move `usage`/`message_log` off `RuntimeConfig` into `Runtime` (or `RuntimeState`)
- [x] Update `WorkerRuntime` to hold `Runtime` instead of `RuntimeConfig`
- [x] Resolve approval callback during `Runtime` creation and reuse per run
- [x] Update `run_invocable` (and/or add new entrypoint) to use `Runtime`
- [x] Update CLI to use `Runtime` for approval policy + UI formatting
- [x] Update `experiments/inv/v2_direct/run.py` to use `Runtime`
- [x] Update docs (`docs/reference.md`, `docs/architecture.md`; optional `README.md`) with the new runtime model
- [x] Add or update tests for approval callback behavior and caching

## Current State
Runtime implemented, call sites and docs updated, tests adjusted; ruff/mypy/pytest run clean.

## Notes
- Runtime should remain entry-agnostic but may provide a session helper for entry-bound runs if needed.
- Approval callbacks currently resolved in `llm_do/runtime/approval.py::resolve_approval_callback`.
- `RuntimeConfig` is already the global object; the new runtime should clarify how it owns or exposes `RuntimeConfig` and how it constructs or reuses `WorkerRuntime`/`CallFrame` per entry.
- Primary example to shrink: `experiments/inv/v2_direct/run.py` should become a minimal runtime-driven script (no manual approval wiring).
