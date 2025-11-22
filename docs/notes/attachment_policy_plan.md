# Attachment enforcement for worker delegation

## Goal
Propagate attachment policies when a worker calls another worker so that
sub-workers cannot read or send files outside the sandboxes the caller already
has access to.

## Requirements
- When `worker_call` receives `attachments`, resolve each path relative to the
  caller's sandbox. Reject any path that escapes or exceeds the caller's
  `AttachmentPolicy` limits (count, total bytes, suffix allow/deny).
- Only allow attachments that the caller has already validated. Ideally they
  should live inside the caller's sandbox roots (no arbitrary `/tmp` files).
- Surface attachment metadata in the approval prompt when a delegated call
  requests approval so operators can see what files will be shared.
- Optionally, allow worker definitions to specify a stricter attachment policy
  for delegated runs (e.g., only `.pdf`, max 10 MB), and enforce it alongside
  the caller's policy.

## Implementation sketch
1. Extend `WorkerContext` with a method like `validate_attachments(paths)` which
   uses the caller's `AttachmentPolicy` and sandbox manager to resolve and vet
   absolute paths.
2. In `_worker_call_tool`, replace the current `Path(path).resolve()` logic with
   a call to `ctx.validate_attachments`; raise if any path is outside allowed
   sandboxes or violates suffix/size limits.
3. Pass the validated attachment list into `run_worker` so the callee receives
   the resolved `Path` objects (still relative to its own sandboxes if needed).
4. Update the CLI approval callback to include attachment names/sizes in the
   payload panel when prompting for `worker.call` approvals.
5. Add tests covering:
   - Delegated attachment allowed/denied by suffix.
   - Attachment too large / too many files.
   - Path escape attempts.
   - Approval prompt shows attachment info.

## Open questions
- Do we allow attachments outside the caller's sandboxes if the CLI originally
  approved them? (Probably not; keeping them sandbox-relative is simpler.)
- Should workers be able to add new attachments beyond the ones they received
  from the CLI? (Maybe via an explicit `sandbox_export` tool in the future.)
