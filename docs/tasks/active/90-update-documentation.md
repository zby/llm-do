# Update Documentation for New Runtime

## Prerequisites
- [x] 70-textual-cli-port-remove-runtime (complete)

## Goal
Update all documentation to reference only the new `llm-run` CLI and `ctx_runtime` architecture.

## Tasks

### README.md
- [ ] Update CLI examples to use `llm-run` instead of `llm-do`
- [ ] Document new flags: `--headless`, `--tui`, `--set`
- [ ] Update installation instructions if needed
- [ ] Remove references to deprecated commands

### Other Docs
- [ ] Check `docs/` directory for outdated references
- [ ] Update any API documentation
- [ ] Ensure examples in docs match `examples/` directory

### Entry Points
Document the two available CLI tools:
- `llm-run` - main CLI for running workers (TUI or headless)
- `llm-do-oauth` - OAuth credential management

## Notes
- Old `llm-do` CLI has been removed
- New runtime is at `llm_do/ctx_runtime/`
- Package version is now 0.3.0
