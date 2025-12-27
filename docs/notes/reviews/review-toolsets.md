# Toolsets Review

## Context
Review of toolsets for bugs, inconsistencies, and overengineering.

## Findings
- `ShellToolset` only blocks metacharacters in `needs_approval()`, while
  `execute_shell()` skips that check and assumes the approval layer handled it.
  Using the shell toolset without an approval wrapper would silently allow
  metacharacters that the docstring claims are blocked.【F:llm_do/shell/toolset.py†L56-L120】【F:llm_do/shell/execution.py†L4-L96】
- Shell rule matching is a simple string prefix check. A short pattern such as
  `"rm"` would also match `"rmdir"` or `"rmx"`, potentially approving more
  commands than intended. There is no shlex-aware or anchored matching to avoid
  over-broad approvals.【F:llm_do/shell/execution.py†L56-L89】
- `get_builtin_toolset()` discards `id` and `max_retries` options even though
  the shell and filesystem toolsets accept them. Built-in toolsets cannot be
  configured for durable IDs or custom retry behavior via the registry entry
  alone.【F:llm_do/ctx_runtime/builtins.py†L31-L47】【F:llm_do/shell/toolset.py†L48-L79】【F:llm_do/filesystem_toolset.py†L28-L60】
- `FileSystemToolset` uses a single `read_approval` flag for both `read_file`
  and `list_files`, so directory listings cannot be approval-gated
  independently from file reads. That coupling may be surprising for users who
  want listings allowed but reads gated (or vice versa).【F:llm_do/filesystem_toolset.py†L46-L119】

## Open Questions
- Should shell metacharacter blocking also run inside `execute_shell()` to avoid
  accidental bypass when the approval wrapper is omitted?
- Would safer rule matching (e.g., shlex token matching or regex anchors)
  reduce accidental approvals compared to the current prefix-only match?
- Do built-in toolsets need a way to forward `id` and `max_retries` so durable
  runs and retry policies can be configured through the registry layer?
- Should `list_files` have its own approval toggle instead of reusing
  `read_approval`?

## Conclusion
TODO
