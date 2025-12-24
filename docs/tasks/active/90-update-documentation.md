# Update Documentation for New Runtime

## Prerequisites
- [x] 70-textual-cli-port-remove-runtime (complete)

## Goal
Update all user-facing documentation to reference the `llm-run` CLI and `llm_do/ctx_runtime` architecture (no `llm-do` CLI behavior).

## Tasks

### Audit / Scope
- [x] Inventory outdated references in README/docs/examples (rg: `llm-do`, old CLI flags, `runtime.py`)
- [x] Decide scope for `docs/notes/` (leave historical unless directly linked from README/docs)

### README.md
- [x] Replace CLI usage blocks with `llm-run` + explicit file lists
- [x] Update entrypoint resolution (use `--entry` or `main` entry)
- [x] Remove deprecated flags/commands (`--dir`, `--tool`, `--input`, `--attachments`, `--no-rich`, `--strict`, `init`)
- [x] Document current flags (`--headless`, `--tui`, `--json`, `-v/-vv`, `--set`, `--approve-all`)
- [x] Keep "llm-do" as project name but call out `llm-run` as the CLI + retain `llm-do-oauth`

### docs/cli.md
- [x] Rewrite Basic Usage for `llm-run <worker.worker> [tools.py...] "prompt"` and `--entry`
- [x] Document flags: `--all-tools`, `--model` (LLM_DO_MODEL), `--set`, `--approve-all`,
  `--verbose`, `--json`, `--headless`, `--tui`, `--debug`
- [x] Update approval behavior for headless/TUI (no `--strict` / `--no-rich`)
- [x] Document stdin prompt behavior + mutually exclusive flags (`--json` vs `--tui`)

### docs/architecture.md
- [x] Update module tree to `llm_do/ctx_runtime/*` + current top-level files
- [x] Update execution flow to `Context.run` + `WorkerEntry` / `ToolEntry` + ApprovalToolset
- [x] Update toolset discovery (worker file toolsets + python toolsets + builtins)
- [x] Remove old runtime references (`runtime.py`, `cli_async.py`, `registry.py`, etc.)

### docs/ui.md
- [x] Replace `llm-do` CLI references with `llm-run`
- [x] Align output modes + TTY detection with current flags (`--tui`, `--headless`, `--json`, `-v`)
- [x] Remove obsolete options (`--no-rich`, `--strict`) and update examples

### docs/bootstrapping.md
- [x] Update bootstrapper invocation to `llm-run` + explicit worker file path
- [x] Verify toolset availability for `worker_bootstrapper` (delegation tools) and update docs
- [x] Update `--set` override paths to current config keys (if changed)
- [x] Confirm generated worker path (`/tmp/llm-do/generated`) remains accurate

### docs/concept.md
- [x] Update CLI examples / references to `llm-run`
- [x] Ensure runtime references point to `ctx_runtime` docs/paths

### Examples + Misc Docs
- [x] Update example READMEs (e.g., `examples/pitchdeck_eval_code_entry/README.md`)
- [x] Update example scripts/comments referencing old CLI
- [x] Ensure docs reference actual `examples/` paths (no `examples-new` drift)

### Entry Points
Document the two available CLI tools wherever CLI usage is introduced:
- `llm-run` - main CLI for running workers (TUI or headless)
- `llm-do-oauth` - OAuth credential management

## Current State
Updated README, `docs/cli.md`, `docs/architecture.md`, `docs/ui.md`,
`docs/bootstrapping.md`, `docs/concept.md`, and example README(s) to `llm-run`
and `ctx_runtime`. Added a bootstrapper status note and aligned CLI help text.

## Notes
- Old `llm-do` CLI has been removed
- New runtime lives in `llm_do/ctx_runtime/`
- Default model still honors `LLM_DO_MODEL`
