# Approval demo: append notes with sandbox writes

This example exists to exercise the interactive approval flow. The worker writes
user-provided notes to a log file in a sandbox, and the `sandbox.write` tool is
configured to require approval each time.

## Files

- `workers/save_note.yaml` – worker definition that treats the entire user
  input as the note text and overwrites `notes/activity.log` (append support
  coming later).
- `notes/` – sandbox directory where the log is stored. It starts empty.

## Run it

```bash
cd examples/approvals_demo
llm-do save_note --model anthropic:claude-haiku-4-5 \
  "Interactive approvals are working"
```

When the worker attempts to call `sandbox_write_text("notes", ...)`, the CLI
prints the payload and prompts you to `[a]pprove`, approve for `[s]ession`,
`[d]eny`, or `[q]uit`. Approving writes the line to `notes/activity.log` and the
final output confirms what was written. Running again will append another line.

Use `--approve-all` if you want to bypass the prompt, or `--strict` to reject all
writes for testing the error path.
