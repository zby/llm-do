# Approval demo: append notes with write approval

This example exists to exercise the interactive approval flow. The worker writes
user-provided notes to a log file, and writes are configured to require approval.

## Files

- `workers/save_note.worker` – worker definition that treats the entire user
  input as the note text and overwrites `notes/activity.log` (append support
  coming later).
- `notes/` – directory where the log is stored. It starts empty.

## Run it

```bash
cd examples/approvals_demo
llm-do save_note --model anthropic:claude-haiku-4-5 \
  "Interactive approvals are working"
```

When the worker attempts to call `write_file("notes/...")`, the CLI
prints the payload and prompts you to `[a]pprove`, approve for `[s]ession`,
`[d]eny`, or `[q]uit`. Approving writes the line to `notes/activity.log` and the
final output confirms what was written. Running again will append another line.

Use `--approve-all` if you want to bypass the prompt, or `--strict` to reject all
writes for testing the error path.
