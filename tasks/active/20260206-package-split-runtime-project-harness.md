# Package Split: Runtime, Project, Harness

## Status
waiting for 20260206-oauth-ownership-boundary

## Prerequisites
- [ ] `tasks/active/20260206-oauth-ownership-boundary.md` (must be resolved before Phase 2/Phase 3 completion)

## Goal
Split the codebase into clear package boundaries so the runtime can be embedded independently while the project linker and CLI/TUI harness evolve without contaminating core APIs.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/runtime.py`, `llm_do/runtime/context.py`, `llm_do/runtime/call.py`, `llm_do/runtime/agent_runner.py`, `llm_do/runtime/contracts.py`
  - `llm_do/runtime/manifest.py`, `llm_do/runtime/agent_file.py`, `llm_do/runtime/discovery.py`, `llm_do/runtime/registry.py`, `llm_do/runtime/entry_resolver.py`, `llm_do/runtime/path_refs.py`, `llm_do/runtime/input_model_refs.py`
  - `llm_do/cli/main.py`, `llm_do/ui/runner.py`, `llm_do/ui/*`
  - `llm_do/toolsets/builtins.py`, `llm_do/toolsets/agent.py`, `llm_do/toolsets/dynamic_agents.py`
  - `tests/runtime/test_build_entry_resolution.py`, `tests/runtime/test_tool_registry_resolution.py`, `tests/runtime/test_toolset_classpath_loading.py`, `tests/runtime/test_manifest.py`, `tests/runtime/test_examples.py`, `tests/runtime/test_agent_recursion.py`, `tests/live/conftest.py`
  - `pyproject.toml`
- Related tasks/notes/docs:
  - `docs/architecture.md` (unified calling convention and harness framing)
  - Current architecture findings (inlined and validated in code on 2026-02-06):
    - `runtime/` currently mixes pure execution concerns with project manifest and file-discovery/linking concerns.
    - Registry construction currently pulls in host built-in toolsets directly (`llm_do/runtime/registry.py` imports `llm_do/toolsets/builtins.py` and `llm_do/toolsets/agent.py`).
    - `llm_do/runtime/__init__.py` currently exports both core runtime types and linker/manifest APIs from one surface.
    - CLI currently imports runtime + linker pieces together (`llm_do/cli/main.py` imports `build_registry`, `resolve_entry`, and `runtime.manifest` APIs directly).
    - Dynamic agent toolset depends on agent-file parsing from `runtime` (`llm_do/toolsets/dynamic_agents.py` imports `runtime.agent_file`).
    - Runtime execution still has host-specific OAuth dependency (`llm_do/runtime/agent_runner.py` imports from `llm_do/oauth`).
    - Packaging is monolithic today (`pyproject.toml` has one distribution and `include = ["llm_do*"]`).
- How to verify / reproduce:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`
  - `llm-do examples/greeter/project.json "hello"`
  - `rg -n "from llm_do\\.runtime\\.(manifest|agent_file|discovery|entry_resolver|registry)" llm_do tests`
  - `rg -n "from \\.\\.toolsets\\.builtins import build_builtin_toolsets" llm_do/runtime`

## Decision Record
- Decision:
  - Use a two-stage split:
  - Stage 1: separate boundaries and publish two packages (`core runtime` and `app`).
  - Stage 2: optionally split `project linker` into its own package only if reuse demand appears.
- Inputs:
  - Need an embeddable runtime with minimal host assumptions.
  - Need to preserve iteration speed on `.agent`/manifest format and CLI/TUI UX.
  - Avoid premature package churn and version-matrix overhead.
- Options:
  - A) Keep one package and only refactor folders.
  - B) Split now into two packages: `core runtime` + `app (project linker + harness)`.
  - C) Split now into three packages: `core runtime` + `project linker` + `harness`.
- Outcome:
  - Choose B now; keep C as a follow-up once linker contracts are stable and reused independently.
- Follow-ups:
  - Re-evaluate three-package split after at least one non-CLI embedding of the linker layer.
  - Document and enforce dependency direction (`core <- project <- harness`).
  - Use validated-first planning: frontload only details confirmed in code now; keep unresolved design items as explicit, time-boxed implementation gates.
  - Defer final decisions that need broader validation (package naming/layout, OAuth ownership boundary) to dedicated steps below.

## Tasks
### Phase 1: Frontloadable Now (validated)
- [ ] Freeze a migration checklist from validated coupling edges in Context (runtime exports, registry imports, CLI imports, dynamic-agent imports, test hotspots).
- [ ] Define a concrete module ownership map for currently-known linker files in `runtime/`: `manifest`, `agent_file`, `discovery`, `entry_resolver`, `path_refs`, `input_model_refs`, `registry`.
- [ ] Refactor registry construction to accept injected host/builtin toolsets (remove direct `runtime -> toolsets.builtins` import coupling).
- [ ] Split runtime public surface by ownership: keep core APIs in `runtime` exports, move linker/manifest exports under app/project boundary.
- [ ] Move directly affected imports for known hotspots: `llm_do/cli/main.py`, `llm_do/toolsets/dynamic_agents.py`, and runtime/linker tests listed in Context.
- [ ] Add dependency-direction checks so core modules cannot import from project/harness modules.

### Phase 2: Focused Validation Gates (do not frontload prematurely)
- [ ] Time-box Stage 1 packaging decision and record outcome (single repo with multiple dists vs other layout, package names, entrypoint ownership), then apply metadata changes.
- [ ] Complete `tasks/active/20260206-oauth-ownership-boundary.md` and apply its decision to this split.

### Phase 3: Finalization
- [ ] Update docs (`README.md`, `docs/architecture.md`) to reflect final package boundaries and dependency direction.
- [ ] Run lint, typecheck, tests, and one CLI smoke test.

## Current State
Task has a validated-first implementation plan. Concrete coupling edges and test hotspots are now inlined, and unresolved high-cost decisions are explicitly isolated as focused validation gates during implementation.
Execution is now blocked on prerequisite task `tasks/active/20260206-oauth-ownership-boundary.md` before Phase 2 and finalization.

## Notes
- Favor clean boundaries over backcompat shims unless a migration blocker appears.
- Keep `.agent` format and manifest semantics unchanged during Stage 1; this task is about packaging and module ownership.
- Keep agent-call semantics (`agent as tool`, name-based dispatch, approval/depth controls) in runtime behavior while relocating linker/harness code.
- Keep validation gates narrow and time-boxed; if a gate expands into broad research, split it into a dedicated task instead of stalling Phase 1 moves.
