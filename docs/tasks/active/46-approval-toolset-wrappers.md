# ApprovalToolset Wrappers (TUI + Headless)

## Prerequisites
- [ ] none

## Goal
Provide separate ApprovalToolset callback wrappers for TUI and headless runs that match the bare API design (Option A).

## Context
- Relevant files/symbols:
  - `llm_do/ctx_runtime/cli.py:_wrap_toolsets_with_approval(...)` (wraps toolsets in `ApprovalToolset`, recursing into `WorkerEntry.toolsets`)
  - `llm_do/ctx_runtime/cli.py:run(...)` (creates `ApprovalMemory()` and wraps `entry.toolsets`)
  - `llm_do/ctx_runtime/cli.py:_run_tui_mode:tui_approval_callback(...)` (async callback -> UI queue)
  - `llm_do/ctx_runtime/cli.py:main()` (CLI flags, incl. `--approve-all`; add `--reject-all` here)
  - `llm_do/ctx_runtime/approval_wrappers.py` (already contains `ApprovalDeniedResultToolset`; add callback helpers here)
  - `tests/runtime/test_approval_wrappers.py` (existing wrapper tests)
- Related tasks/notes/docs:
  - `docs/notes/approval-toolset-bare-api.md` (Option A + memoizing callback sketch)
  - `docs/notes/approval_wrapping_architecture.md` (why recursion exists; other options)
  - Historical: the previous async CLI had `--strict` (auto-deny approvals); that flag was removed during runtime consolidation and should return as `--reject-all`.
- Dependency reality:
  - Current env/lock pins `pydantic_ai_blocking_approval==0.8.0`; `ApprovalToolset.__init__` still accepts `memory=...` and caches approvals via `ApprovalMemory` when `ApprovalDecision.remember == "session"` (keyed by tool name + deterministic JSON of args; only cached approvals bypass prompts).
  - Design target is the 0.9.x bare API (no `ApprovalMemory`), so llm-do must move session caching into callback wrappers before upgrading.
- How to verify / reproduce:
  - `uv run pytest -k approval_wrappers`
  - Manual smoke (requires API key):
    - `cd examples/approvals_demo && llm-do --tui main.worker "note"` (prompt for filesystem tool approval)
    - `cd examples/approvals_demo && llm-do --headless main.worker "note"` (expect denial without `--approve-all`)
    - `cd examples/approvals_demo && llm-do --headless --approve-all main.worker "note"` (expect success)
    - After adding `--reject-all`: `cd examples/approvals_demo && llm-do --tui --reject-all main.worker "note"` (expect denial without prompting)

## Tasks
- [x] Gather current call sites + constraints (CLI run path, TUI callback, existing wrappers/tests)
- [x] Draft Proposed Resolutions (API, caching, headless policy, overrides)
- [ ] Implement TUI wrapper with lightweight session caching
- [ ] Implement headless wrapper that enforces config/CLI policy (no memoization)
- [ ] Add `--reject-all` CLI flag (symmetry with `--approve-all`) and make it mutually exclusive with `--approve-all`
- [ ] Wire wrappers into CLI/direct Python entry points
- [ ] Add/update tests and docs as needed

## Current State
Option A chosen in `docs/notes/approval-toolset-bare-api.md`.

Current CLI implementation:
- Uses `ApprovalMemory()` + `ApprovalToolset(..., memory=memory, ...)` in `llm_do/ctx_runtime/cli.py`.
- Defines `tui_approval_callback(...)` inline in `_run_tui_mode` and a headless default callback that raises `PermissionError`.

Proposed resolutions are captured below; task is ready to implement.

## Notes
- In 0.9.x (bare API), `ApprovalToolset` no longer has `ApprovalMemory`, so memoization must live in the callback wrapper (keep parity with current 0.8.0 session behavior).
- Headless policy is deterministic (config + CLI args), so caching adds no value.
- Keep callbacks sync for non-interactive flows.
- Headless wrapper must rely on `ApprovalToolset` to skip callbacks for
  pre-approved tools (config-based or `SupportsNeedsApproval`).

## Proposed Resolutions
- Wrapper API + location: add `make_tui_approval_callback(...)` and
  `make_headless_approval_callback(...)` in `llm_do/ctx_runtime/approval_wrappers.py`.
- Cache key strategy (TUI): `(request.tool_name, json.dumps(request.tool_args, sort_keys=True, default=str))`.
  Exclude `description` so "remember" persists across prompt text changes.
- `--approve-all` behavior: always auto-approve (headless + TUI), and never prompt the UI.
- `--reject-all` behavior: always auto-deny (headless + TUI), and never prompt the UI.
- Headless denial behavior (default without `--approve-all`): raise `PermissionError` with a `--approve-all` hint (keep current CLI message clarity).
- Overrides: keep minimal; allow optional `cache` and `cache_key_fn` for tests.
- Headless behavior depends on `ApprovalToolset` to bypass callbacks when
  tools are pre-approved via config or toolset logic.

## Design Check
- `pydantic_ai_blocking_approval` 0.9.x removes `ApprovalToolset(..., memory=...)`;
  existing CLI code passes `ApprovalMemory`, so llm-do must move session caching
  into callback wrappers before upgrading.
- TUI callback is async today; memoizing wrapper must be async-aware (cache
  check before awaiting, and normalize sync/async results).
- `--approve-all` must short-circuit approval in both headless and TUI flows.
- `--reject-all` must short-circuit approval in both headless and TUI flows.
- Keep entry-level approvals (`entry.requires_approval`) separate from tool-level
  approvals; wrappers only apply to the tool-level ApprovalToolset flow.
