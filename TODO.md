# TODO

## CLI enhancements

- [x] **Phase 1 (MVP)**: Add `--set KEY=VALUE` for simple runtime config overrides with dot notation and type inference. See `docs/cli.md` for usage.
- [ ] **Phase 2 & 3**: Add `--override JSON` for complex overrides, list operators (`+=`, `-=`), override profiles, and validation mode. See `docs/notes/todos/future_work.md` for details.

## Runtime polish

- [x] Surface attachment approval/context UX in the CLI (prompts instead of auto-approving everything). Attachments passed to `worker_call` now go through `sandbox.read` approval with full metadata (path, size, target worker).
- [ ] Add a "defer and resume" path for approval-required tools so long runs can pause and continue later. (Complex - requires state serialization and agent resume mechanism.)

## Docs & guidance

- [ ] Expand AGENTS/README with a short "Worker authoring checklist".

## Bootstrapper

- [ ] Implement automatic iterative refinement: bootstrapper should read the created worker, call it, evaluate output, and refine the definition if needed.

## Tool Approval Enhancements

- [ ] **Rich Presentation (Phase 2)**: Implement `ApprovalPresentation` rendering in CLI
  - Display diffs with syntax highlighting for file edits
  - Show syntax-highlighted content for new file creation
  - Add `[v]iew full` pager option for large content
  - Support presentation types: `text`, `diff`, `file_content`, `command`, `structured`
  - Lazy presentation generation (only compute diffs when actually prompting)

## Security & Sandboxing

- [ ] **OS-level sandbox enforcement**: Add Seatbelt (macOS) and bubblewrap (Linux) wrappers for shell subprocess isolation. Wrap shell commands in OS-level sandbox to provide defense-in-depth beyond application-level path validation.
  - Derive OS sandbox profile from tool configurations (sandbox paths, shell rules)
  - Key invariant: OS sandbox must never be less restrictive than Python/tool config
  - Add `require_os_sandbox` option to fail fast if OS sandbox unavailable
  - Support `os_sandbox_fallback: refuse_tools` for degraded mode

- [ ] **Sandbox relative path security review**: Audit sandbox and shell tools for relative path handling vulnerabilities.
  - Review `filesystem_sandbox.py` path normalization (`.resolve()`, symlink handling)
  - Review `shell.py` path argument extraction and validation (`extract_path_arguments`, `validate_paths_in_sandbox`)
  - Test edge cases: `../../`, symlinks, absolute paths in sandboxed contexts
  - Consider blocking `..` in shell path arguments entirely when `sandbox_paths` is set
  - Document safe patterns for shell commands in sandboxes

## Location-Independent Workers

**Status:** ✅ **Completed (Phase 1)**

**Solution implemented:**
- [x] Shell commands now run from user's current working directory by default (not registry root)
- [x] Added `shell_cwd` field to WorkerDefinition for workers that need specific directories
- [x] Overridable at runtime: `--set shell_cwd=/some/project`
- [x] Worker creation still uses `registry.root/workers/generated/` (registry acts as "project root")

**Remaining (future work):**
- [ ] Support absolute sandbox paths (currently only relative to registry root)
- [ ] Template variables in paths (e.g., `{CWD}`, `{REGISTRY_ROOT}`)

**Benefits achieved:** Workers with shell tools now work from user's current directory, making `code_analyzer` and similar workers location-independent.
