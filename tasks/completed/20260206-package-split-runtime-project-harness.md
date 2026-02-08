# Package Split: Runtime, Project, Harness

## Status
completed

## Prerequisites
- [x] `tasks/completed/20260206-oauth-ownership-boundary.md` (must be resolved before Phase 2/Phase 3 completion)

## Goal
Split the codebase into clear package boundaries so the runtime can be embedded independently while the project linker and CLI/TUI harness evolve without contaminating core APIs.

## Context
- Relevant files/symbols:
  - Core runtime: `llm_do/runtime/runtime.py`, `llm_do/runtime/context.py`, `llm_do/runtime/call.py`, `llm_do/runtime/agent_runner.py`, `llm_do/runtime/contracts.py`, `llm_do/runtime/approval.py`, `llm_do/runtime/args.py`, `llm_do/runtime/events.py`
  - Linker/project (currently in runtime/): `llm_do/runtime/manifest.py`, `llm_do/runtime/agent_file.py`, `llm_do/runtime/discovery.py`, `llm_do/runtime/registry.py`, `llm_do/runtime/entry_resolver.py`, `llm_do/runtime/path_refs.py`, `llm_do/runtime/input_model_refs.py`
  - Harness: `llm_do/cli/main.py`, `llm_do/ui/runner.py`, `llm_do/ui/adapter.py`, `llm_do/ui/*`
  - Toolsets: `llm_do/toolsets/builtins.py`, `llm_do/toolsets/agent.py`, `llm_do/toolsets/dynamic_agents.py`
  - Tests: `tests/runtime/test_build_entry_resolution.py`, `tests/runtime/test_tool_registry_resolution.py`, `tests/runtime/test_toolset_classpath_loading.py`, `tests/runtime/test_manifest.py`, `tests/runtime/test_examples.py`, `tests/runtime/test_agent_recursion.py`, `tests/live/conftest.py`
  - `pyproject.toml`
- Related tasks/notes/docs:
  - `docs/architecture.md` (unified calling convention and harness framing)
  - `tasks/backlog/20260202-deferred-handler-approval-cleanup.md` (approval-wrapping migration is explicitly deferred; not part of this split task)
  - Current architecture findings (inlined and validated in code on 2026-02-06):
    - `runtime/` currently mixes pure execution concerns with project manifest and file-discovery/linking concerns.
    - Registry construction currently pulls in host built-in toolsets directly (`llm_do/runtime/registry.py` imports `llm_do/toolsets/builtins.py` and `llm_do/toolsets/agent.py`).
    - `llm_do/runtime/__init__.py` currently exports both core runtime types and linker/manifest APIs from one surface.
    - CLI currently imports runtime + linker pieces together (`llm_do/cli/main.py` imports `build_registry`, `resolve_entry`, and `runtime.manifest` APIs directly).
    - Dynamic agent toolset depends on agent-file parsing from `runtime` (`llm_do/toolsets/dynamic_agents.py` imports `runtime.agent_file`).
    - **Bidirectional toolsets ↔ runtime coupling**: `runtime/registry.py` imports `toolsets.builtins` and `toolsets.agent` (claim 1), while `toolsets/agent.py` reaches back into `runtime.approval`, `runtime.args`, and `runtime.contracts` (lines 12–14). The reverse direction is correct for the target dependency arrow (toolsets are app-layer), but the forward direction (registry → toolsets) must be broken.
    - `toolsets/dynamic_agents.py` also imports `runtime.approval` and `runtime.contracts` beyond agent_file (lines 21–22).
    - `ui/runner.py` imports `runtime.contracts.MessageLogCallback` and `runtime.events.RuntimeEvent` (lines 15–17).
    - `ui/adapter.py` imports `runtime.events` (line 18).
    - Runtime currently imports `toolsets.loader` aliases/helpers across core modules; this coupling should be removed in Phase 1 by switching to direct PydanticAI types and moving resolver logic to linker/project ownership.
    - `toolsets.loader` coupling is broader than `registry.py`; current runtime imports span 7 modules:
      - `llm_do/runtime/__init__.py`: `ToolDef`, `ToolsetDef`
      - `llm_do/runtime/contracts.py`: `ToolDef`, `ToolsetDef`, `is_tool_def`, `is_toolset_def`
      - `llm_do/runtime/call.py`: `ToolDef`, `ToolsetDef`, `tool_def_name`
      - `llm_do/runtime/context.py`: `ToolDef`, `ToolsetDef`
      - `llm_do/runtime/runtime.py`: `ToolDef`, `ToolsetDef`
      - `llm_do/runtime/discovery.py`: `ToolDef`, `ToolsetDef`, `is_tool_def`, `is_toolset_def`, `tool_def_name`
      - `llm_do/runtime/registry.py`: `ToolDef`, `ToolsetDef`, `resolve_tool_defs`, `resolve_toolset_defs`
    - `discovery.py` is classified as linker/project; its loader coupling is acceptable only after it is relocated out of the core runtime package boundary.
    - Runtime currently imports `toolsets.approval`; that decoupling is tracked separately in `tasks/backlog/20260202-deferred-handler-approval-cleanup.md` and is out of scope for this task.
    - OAuth ownership boundary has been resolved via injected runtime callbacks (`auth_mode` + provider/override resolvers wired from CLI).
    - Packaging is monolithic today (`pyproject.toml` has one distribution and `include = ["llm_do*"]`).
- How to verify / reproduce:
  - Acceptance criteria:
    - Core runtime modules do not import from app/harness surfaces (`project/linker`, `cli`, `ui`) and do not import `toolsets.loader`.
    - `toolsets.approval` runtime coupling remains allowed only as a temporary seam tracked by `tasks/backlog/20260202-deferred-handler-approval-cleanup.md`.
    - `runtime/registry.py` no longer imports `toolsets.builtins` or `toolsets.agent`; host layer assembles and injects toolsets.
    - CLI/UI/toolset/runtime-linker tests compile and run with updated import paths.
    - Package split behavior preserves runtime execution and CLI smoke path.
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`
  - `uv run pytest tests/runtime/test_dependency_direction.py`
  - `llm-do examples/greeter/project.json "hello"`
  - `rg -n "from llm_do\\.runtime\\.(manifest|agent_file|discovery|entry_resolver|registry)" llm_do tests` (expected only where linker/project APIs are intentionally used)
  - `rg -n "from \\.\\.toolsets\\.(builtins|agent)" llm_do/runtime/registry.py` (expected no matches)
  - `rg -n "from \\.\\.toolsets\\.loader|from llm_do\\.toolsets\\.loader" llm_do/runtime` (expected no matches)

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
  - Chose B at module/package-boundary level now (`llm_do/runtime` core, `llm_do/project` linker, `llm_do/cli` + `llm_do/ui` harness) while keeping a single distribution in `pyproject.toml`.
  - Keep C as a follow-up once linker contracts are stable and reused independently.
- Packaging decision (2026-02-08 implementation):
  - Keep single distribution (`llm_do*`) for Stage 1 to avoid premature multi-dist versioning overhead.
  - Treat boundary enforcement (imports/tests/public surfaces) as the current contractual split.
- Follow-ups:
  - Re-evaluate three-package split after at least one non-CLI embedding of the linker layer.
  - Document and enforce dependency direction (`core <- project <- harness`).
  - Use validated-first planning: frontload only details confirmed in code now; keep unresolved design items as explicit, time-boxed implementation gates.
  - Defer final decisions that need broader validation (package naming/layout, distribution metadata layout) to dedicated steps below.
  - Keep approval-wrapper ownership cleanup out of this task; execute it under `tasks/backlog/20260202-deferred-handler-approval-cleanup.md`.

## Tasks
### Phase 1A: No-code Frontloading Gates (validated)
- [x] **1a. Module ownership map (verified).** Classified every `runtime/` module as core or linker. Linker: `manifest`, `agent_file`, `discovery`, `entry_resolver`, `path_refs`, `input_model_refs`, `registry`. Core: `runtime`, `context`, `call`, `agent_runner`, `contracts`, `approval`, `args`, `events`. Verified in task context on 2026-02-08.
- [x] **1b. Migration checklist.** Frozen/implemented via concrete move + import rewrites listed in Current State update (2026-02-08).

### Phase 1B: Implementation Moves
- [x] **1c. Inject host/builtin toolsets into registry.** `llm_do/project/registry.py` now accepts `extra_toolsets` and `agent_toolset_factory`; `llm_do/cli/main.py` assembles host toolsets via `llm_do/project/host_toolsets.py` and injects them.
- [x] **1d. Lock linker/app target layout path.** Implemented with new `llm_do/project/` package owning linker/manifest/discovery/registry/entry-resolution modules.
- [x] **1e. Remove `runtime -> toolsets.loader` coupling (type-surface decision + migration).** Chose runtime-owned alias/helpers in `llm_do/runtime/tooling.py`; migrated runtime modules; moved tool resolution ownership to `llm_do/project/tool_resolution.py` (with compatibility re-export in `llm_do/toolsets/loader.py`).
- [x] **1f. Split runtime public surface.** `llm_do/runtime/__init__.py` now exports core runtime APIs only; linker APIs are exported via `llm_do/project/__init__.py`.
- [x] **1g. Relocate hotspot imports.** Updated CLI/UI/dynamic-agent imports and impacted runtime/live tests to new `llm_do.project` paths.
- [x] **1h. Dependency-direction enforcement.** Added `tests/runtime/test_dependency_direction.py` to enforce no core runtime imports from project/cli/ui and no `runtime -> toolsets.loader|builtins|agent` (with `toolsets.approval` seam allowed).

### Phase 2: Focused Validation Gates (do not frontload prematurely)
- [x] **2a. Time-box packaging decision.** Completed during implementation pass on 2026-02-08.
- [x] **2b. Record decision and rationale.** Decision recorded above: keep one distribution for now, enforce boundaries via module ownership + dependency tests.
- [x] **2c. Apply metadata changes.** No distribution metadata split required for Stage 1 (existing `include = ["llm_do*"]` already includes `llm_do/project`); verification rerun completed.
- [x] Complete `tasks/completed/20260206-oauth-ownership-boundary.md` and apply its decision to this split.

### Phase 3: Finalization
- [x] Update docs (`README.md`, `docs/architecture.md`) to reflect final package boundaries and dependency direction.
- [x] Run lint, typecheck, tests, and one CLI smoke test.

## Current State
Task reviewed and revised (2026-02-06). Changes from review:
- Added 3 missing coupling edges: `toolsets/agent.py` → runtime (bidirectional), `ui/runner.py` → runtime.contracts/events, `ui/adapter.py` → runtime.events.
- Added `approval.py`, `args.py`, `events.py` to module inventory — these are core runtime, not linker.
- Reordered Phase 1: ownership map is now an explicit prerequisite for migration checklist and all subsequent items.
- Added concrete design direction for registry injection (parameter-based, caller assembles).
- Specified dependency-direction enforcement mechanism (pytest-based grep).
- Time-boxed Phase 2 packaging gate (1 session, default to multi-dist).
Scope alignment update (2026-02-08):
- Explicitly deferred `toolsets.approval` decoupling to `tasks/backlog/20260202-deferred-handler-approval-cleanup.md`.
- Added explicit Phase 1 implementation step to remove `runtime -> toolsets.loader` coupling.
- Updated acceptance criteria/verification to enforce no runtime imports of `toolsets.loader`.
Task refinement update (2026-02-08, follow-up review):
- Expanded `toolsets.loader` inventory to all 7 runtime modules currently coupled to loader helpers/types.
- Reordered Phase 1B to frontload isolated registry injection and layout lock-in before cross-cutting type migration.
- Added explicit type-surface decision gate for post-split ownership of `ToolDef`/`ToolsetDef`.
- Marked module ownership map step as verified-complete and kept migration checklist as the active gate.
OAuth ownership prerequisite is resolved (callback-based seam implemented), so this task is unblocked for remaining split work.
Implementation completion update (2026-02-08):
- Moved linker modules from `llm_do/runtime/` to new `llm_do/project/` package and added `llm_do/project/__init__.py`.
- Added host-toolset assembly helpers in `llm_do/project/host_toolsets.py`.
- Added runtime-owned tool type surface in `llm_do/runtime/tooling.py` and removed runtime imports of `toolsets.loader`.
- Added project-owned resolver helpers in `llm_do/project/tool_resolution.py`; `llm_do/toolsets/loader.py` is now a compatibility re-export layer.
- Updated `llm_do/runtime/__init__.py` to core-only exports and rewired callers/tests to `llm_do.project`.
- Added `tests/runtime/test_dependency_direction.py` for import-boundary enforcement.
- Addressed a runtime/toolsets circular import by making `llm_do/toolsets/__init__.py` lazily expose `DynamicAgentsToolset`.
- Verification run complete:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`
  - `LLM_DO_MODEL=test .venv/bin/python -m llm_do.cli.main examples/greeter/project.json "hello"`

## Notes
- Favor clean boundaries over backcompat shims unless a migration blocker appears.
- Keep `.agent` format and manifest semantics unchanged during Stage 1; this task is about packaging and module ownership.
- Keep agent-call semantics (`agent as tool`, name-based dispatch, approval/depth controls) in runtime behavior while relocating linker/harness code.
- Keep validation gates narrow and time-boxed; if a gate expands into broad research, split it into a dedicated task instead of stalling Phase 1 moves.
