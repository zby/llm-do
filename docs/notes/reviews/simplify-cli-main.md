# Simplify: cli/main.py

## Context
Periodic simplification review of `llm_do/cli/main.py` and its direct internal
dependencies (`llm_do.runtime.*`, `llm_do.ui.*`).

## Findings
- Unused `run()` duplicates runtime + entry setup; no internal references found,
  so deleting or moving to a public runtime API would shrink `llm_do/cli/main.py`.
- Entry rebuild per chat turn: `_make_entry_factory` resolves paths and calls
  `build_entry` on every factory call; `run_tui` calls this for each chat turn.
  If hot-reload is not required, build once and pass `entry=` to `run_tui` or
  `run_headless`, dropping the factory and repeated path resolution.
- Manual exclusivity checks could be argparse groups: `--headless` vs `--tui`
  and `prompt` vs `--input-json` are enforced manually; a mutually exclusive
  group would remove conditionals (but error strings/tests would change).
- `input_data` is always a dict in this CLI, so `isinstance(input_data, dict)`
  around `initial_prompt` is redundant; the "No input provided" error is
  duplicated in the TTY vs non-TTY branch.
- Logging/verbosity wiring is repeated: message-log callback creation and
  backend wiring are duplicated in the TUI and headless branches; consider a
  small helper or a single `run_ui` call to avoid repeated branching.
- Manifest `return_permission_errors` is ignored in TUI mode: CLI hard-codes
  `return_permission_errors=True` when calling `run_tui`, so the manifest flag
  only matters in headless mode. Either honor it in TUI or remove it from the
  UI path to reduce unused flexibility.

## Open Questions
- Is per-turn entry rebuild intended to support hot-reload during chat, or can
  the CLI reuse a single built entry?
- Are CLI error strings part of the expected interface? If not, argparse-managed
  exclusivity could simplify checks.
- Should `return_permission_errors` be manifest-driven for both headless and
  TUI, or always-on in TUI (and removed from the manifest surface)?

## 2026-02-01 Review

- `run()` is still unused outside this module (no imports found). Consider
  removing it or moving it into a public runtime helper to reduce CLI surface.
- Entry building is duplicated: `run()` builds registry + entry, and
  `_make_entry_factory()` does the same per call. If hot reload is not needed
  for chat, build once and pass `entry=`/`agent_registry=` into UI runners.
- Input selection duplicates error paths (TTY vs non-TTY) and the
  "no input provided" message is repeated; a small helper can centralize
  input acquisition + errors.
- Message-log callback and backend wiring is repeated in TUI vs headless
  branches. A shared helper (or `run_ui`) would shrink branching.
- TUI always sets `return_permission_errors=True`, ignoring the manifest
  setting. Either honor it or remove it from the TUI path to cut unused
  flexibility.

## Open Questions (2026-02-01)
- Do we still need `run()` as a public helper, or can the CLI exclusively use
  `run_tui`/`run_headless`?
- Is entry rebuild per chat turn intentional (hot reload), or can we cache the
  entry/registry for the session?

## 2026-02-09 Review
- `_make_entry_factory()` still rebuilds paths, registry, and entry per call; this is only needed for hot reload. If chat hot reload is not intentional, build once and pass `entry` + `agent_registry` to `run_ui`.
- `main()` still owns argument validation, manifest loading, input normalization, verbosity wiring, and UI mode branching. Extracting `resolve_input_data()` and `resolve_backends()` would shrink branch duplication.
- TUI path still hard-codes `return_permission_errors=True` while headless uses manifest runtime config; this remains an unused-flexibility seam.
