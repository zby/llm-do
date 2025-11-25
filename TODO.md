# TODO

## Runtime polish

- [ ] Expose per-sandbox aliases when generating `sandbox_*` tool calls so orchestration instructions can mention `sandbox_write_text("evaluations", …)` without boilerplate.
- [ ] Surface attachment approval/context UX in the CLI (prompts instead of auto-approving everything).
- [ ] Add a “defer and resume” path for approval-required tools so long runs can pause and continue later.

## Docs & guidance

- [ ] Expand AGENTS/README with a short “Worker authoring checklist”.

## Bootstrapper

- [ ] Implement automatic iterative refinement: bootstrapper should read the created worker, call it, evaluate output, and refine the definition if needed.

## Security & Sandboxing

- [ ] OS-level sandbox enforcement (Phase 6-7): Add Seatbelt (macOS) and bubblewrap (Linux) wrappers for shell subprocess isolation. See `docs/notes/todos/future_work.md` for details.
