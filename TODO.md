# TODO

## CLI enhancements

- [ ] Add `--set key=value` or `--override JSON` to override any worker config from command line (sandbox paths, model, allow_workers, tool_rules, etc.)

## Runtime polish

- [x] Surface attachment approval/context UX in the CLI (prompts instead of auto-approving everything). Attachments passed to `worker_call` now go through `sandbox.read` approval with full metadata (path, size, target worker).
- [ ] Add a "defer and resume" path for approval-required tools so long runs can pause and continue later. (Complex - requires state serialization and agent resume mechanism.)

## Docs & guidance

- [ ] Expand AGENTS/README with a short "Worker authoring checklist".

## Bootstrapper

- [ ] Implement automatic iterative refinement: bootstrapper should read the created worker, call it, evaluate output, and refine the definition if needed.

## Security & Sandboxing

- [ ] **OS-level sandbox enforcement**: Add Seatbelt (macOS) and bubblewrap (Linux) wrappers for shell subprocess isolation. Wrap shell commands in OS-level sandbox to provide defense-in-depth beyond application-level path validation.

- [ ] **Sandbox relative path security review**: Audit sandbox and shell tools for relative path handling vulnerabilities.
  - Review `filesystem_sandbox.py` path normalization (`.resolve()`, symlink handling)
  - Review `shell.py` path argument extraction and validation (`extract_path_arguments`, `validate_paths_in_sandbox`)
  - Test edge cases: `../../`, symlinks, absolute paths in sandboxed contexts
  - Consider blocking `..` in shell path arguments entirely when `sandbox_paths` is set
  - Document safe patterns for shell commands in sandboxes

## Location-Independent Workers

**Problem:** Workers must be run from their own directory. Relative paths in sandboxes and shell commands only work from specific locations. This limits reusability - examples cannot easily be run from arbitrary locations.

**Proposed solutions:**
- [ ] Add configurable "project root" that workers can reference
- [ ] Let workers specify their shell working directory in the definition
- [ ] Support absolute sandbox paths (currently only relative)
- [ ] Add runtime path parameters like `--cwd` or `--project-root` CLI flags

**Benefits:** Run `llm-do code_analyzer` from anywhere, analyze any directory. Reusable workers that work across different project structures.
