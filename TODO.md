# TODO

## CLI Enhancements

- [x] `--set KEY=VALUE` for runtime config overrides
- [ ] `--override JSON` for bulk overrides
- [ ] List operators (`+=`, `-=`) for allow_workers, custom_tools
- [ ] Override profiles (`--profile production`)
- [ ] Environment variable expansion in `--set`

## Runtime

- [x] Attachment approval UX in CLI
- [x] Shell commands run from user's cwd by default
- [ ] Defer/resume for long approval-gated runs (complex)

## Worker System

- [ ] **Per-worker tool interface**: Expose allowed workers as first-class tools (auto-generate tool from worker description)
  - See [workers-as-tools.md](docs/notes/workers-as-tools.md) for design discussion
- [ ] **Dynamic sandbox expansion**: Runtime approval to expand sandbox boundaries
  - See [dynamic-sandbox-expansion.md](docs/notes/dynamic-sandbox-expansion.md) for design
- [ ] Support absolute sandbox paths
- [ ] Template variables in paths (`{CWD}`, `{REGISTRY_ROOT}`)

## Toolset Architecture

- [ ] **Plugin architecture**: Workers declare toolsets by class name, dynamic loading
  - See [design doc](docs/notes/toolset_plugin_architecture.md)
  - Add `create()` classmethod to `ApprovalToolset` in `pydantic-ai-blocking-approval`
  - Inner toolsets accept `(config, context)` for uniform DI
  - Generic toolset loading in `execution.py` (no toolset-specific code)

## Bootstrapper

- [ ] Iterative refinement: create worker → run → evaluate → refine

## Security

- [x] ~~**OS-level sandbox**~~: Decided against built-in OS sandbox - recommend Docker for isolation
  - See [dynamic-sandbox-expansion.md](docs/notes/dynamic-sandbox-expansion.md) for rationale
- [ ] **Path security audit**: Review relative paths, symlinks, `..` handling in sandbox/shell

## Docs

- [ ] Worker authoring checklist in AGENTS.md
