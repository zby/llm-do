# ApprovalToolset Wrappers (TUI + Headless)

## Prerequisites
- [x] none

## Goal
Provide separate ApprovalToolset callback wrappers for TUI and headless runs using the 0.9.0 bare API.

## Context
- Relevant files/symbols:
  - `llm_do/ctx_runtime/cli.py:_wrap_toolsets_with_approval(...)` (wraps toolsets in `ApprovalToolset`, recursing into `WorkerEntry.toolsets`)
  - `llm_do/ctx_runtime/cli.py:run(...)` (wraps `entry.toolsets`)
  - `llm_do/ctx_runtime/cli.py:_run_tui_mode:tui_approval_callback(...)` (async callback -> UI queue)
  - `llm_do/ctx_runtime/cli.py:main()` (CLI flags, incl. `--approve-all` and `--reject-all`)
  - `llm_do/ctx_runtime/approval_wrappers.py` (already contains `ApprovalDeniedResultToolset`; add callback helpers here)
  - `tests/runtime/test_approval_wrappers.py` (existing wrapper tests)
- Related tasks/notes/docs:
  - `docs/notes/approval-toolset-bare-api.md` (Option A + memoizing callback sketch)
  - `docs/notes/approval_wrapping_architecture.md` (why recursion exists; other options)
  - Historical: the previous async CLI had `--strict` (auto-deny approvals); that flag was removed during runtime consolidation and should return as `--reject-all`.
- **0.9.0 API** (from `../pydantic-ai-blocking-approval`):
  - `ApprovalToolset(inner, approval_callback, config)` — no `memory` param, session caching is caller-managed
  - `ApprovalResult` with factory methods: `.blocked(reason)`, `.pre_approved()`, `.needs_approval()`
  - `ApprovalRequest(tool_name, tool_args, description)` — passed to callback
  - `ApprovalDecision(approved, note, remember)` — returned by callback
  - `ApprovalCallback = Callable[[ApprovalRequest], ApprovalDecision | Awaitable[ApprovalDecision]]`
  - Exceptions: `ApprovalError` (base, extends `PermissionError`), `ApprovalDenied`, `ApprovalBlocked`
  - Protocols: `SupportsNeedsApproval` (can return sync or async), `SupportsApprovalDescription`
- How to verify / reproduce:
  - `uv run pytest -k approval_wrappers`
  - Manual smoke (requires API key):
    - `cd examples/approvals_demo && llm-do --tui main.worker "note"` (prompt for filesystem tool approval)
    - `cd examples/approvals_demo && llm-do --headless main.worker "note"` (expect denial without `--approve-all`)
    - `cd examples/approvals_demo && llm-do --headless --approve-all main.worker "note"` (expect success)
    - `cd examples/approvals_demo && llm-do --tui --reject-all main.worker "note"` (expect denial without prompting)

## Tasks
- [x] Gather current call sites + constraints (CLI run path, TUI callback, existing wrappers/tests)
- [x] Draft Proposed Resolutions (API, caching, headless policy, overrides)
- [x] Update pyproject.toml to use local pydantic-ai-blocking-approval (`../pydantic-ai-blocking-approval`)
- [x] Implement TUI wrapper with lightweight session caching
- [x] Implement headless wrapper that enforces config/CLI policy (no memoization)
- [x] Add `--reject-all` CLI flag (symmetry with `--approve-all`) and make it mutually exclusive with `--approve-all`
- [x] Wire wrappers into CLI/direct Python entry points
- [x] Add/update tests and docs as needed

## Current State
Completed.

- Migrated to `pydantic-ai-blocking-approval` 0.9.0 bare API (no `ApprovalMemory`).
- Added `make_tui_approval_callback(...)` (session caching) and `make_headless_approval_callback(...)` (deterministic policy).
- Wired wrappers into CLI `run(...)` and TUI mode; updated direct Python example usage.
- Verified: `uv run pytest` (all tests pass).

## Notes
- 0.9.0 `ApprovalToolset(inner, approval_callback, config)` — no `memory` param
- Session caching is caller-managed via callback wrappers (see README example `with_session_cache`)
- Headless policy is deterministic (config + CLI args), so caching adds no value
- Callbacks can be sync or async (`ApprovalCallback` type alias)
- `needs_approval` protocol method can be sync or async (toolset awaits if needed)
- Exceptions: `ApprovalDenied` (user denied), `ApprovalBlocked` (policy blocked) — both extend `ApprovalError` which extends `PermissionError`
- Headless wrapper relies on `ApprovalToolset` config to skip callbacks for pre-approved tools

## Proposed Resolutions
- Wrapper API + location: add `make_tui_approval_callback(...)` and
  `make_headless_approval_callback(...)` in `llm_do/ctx_runtime/approval_wrappers.py`.
- Cache key strategy (TUI): `(request.tool_name, json.dumps(request.tool_args, sort_keys=True, default=str))`.
  Exclude `description` so "remember" persists across prompt text changes.
- `--approve-all` behavior: return `ApprovalDecision(approved=True)` immediately (headless + TUI).
- `--reject-all` behavior: return `ApprovalDecision(approved=False, note="--reject-all")` immediately (headless + TUI).
- Headless denial behavior (default without `--approve-all`): return `ApprovalDecision(approved=False, note="Use --approve-all for headless")`.
- Overrides: keep minimal; allow optional `cache` and `cache_key_fn` for tests.

## Design Check
- TUI callback is async today; memoizing wrapper must be async-aware (cache
  check before awaiting, and normalize sync/async results).
- `--approve-all` must short-circuit approval in both headless and TUI flows.
- `--reject-all` must short-circuit approval in both headless and TUI flows.
- Keep entry-level approvals (`entry.requires_approval`) separate from tool-level
  approvals; wrappers only apply to the tool-level ApprovalToolset flow.
