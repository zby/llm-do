# TODO

## CLI enhancements

- [ ] Add `--set key=value` or `--override JSON` to override any worker config from command line (sandbox paths, model, allow_workers, tool_rules, etc.)

## Runtime polish

- [ ] Surface attachment approval/context UX in the CLI (prompts instead of auto-approving everything). Attachments passed to `worker_call` should go through approval similar to file reads.
- [ ] Add a "defer and resume" path for approval-required tools so long runs can pause and continue later. (Complex - requires state serialization and agent resume mechanism.)

## Docs & guidance

- [ ] Expand AGENTS/README with a short “Worker authoring checklist”.

## Bootstrapper

- [ ] Implement automatic iterative refinement: bootstrapper should read the created worker, call it, evaluate output, and refine the definition if needed.

## Security & Sandboxing

- [ ] OS-level sandbox enforcement (Phase 6-7): Add Seatbelt (macOS) and bubblewrap (Linux) wrappers for shell subprocess isolation. See `docs/notes/todos/future_work.md` for details.
