# Toolset Review Findings

## Context
Review requested for toolset-related modules in llm-do to identify bugs, inconsistencies,
overengineering, and other issues.

## Findings
- **Allowlist bypass in delegation:** `worker_call` accepts any worker name without checking
  configured tools, so enabling `worker_call` allows invoking arbitrary workers even if
  they are not exposed as `_agent_*`. This undermines the allowlist model.
- **Custom tool approvals ignored:** `toolsets.custom` config includes `pre_approved`, but
  `CustomToolset` only uses config to whitelist tools. Approval behavior is determined by
  `_approval_config`, which is not wired to custom tool entries, so per-tool approvals are
  silently ignored.
- **Read approvals inconsistent for listing:** `list_files` is always pre-approved even when
  `read_approval` is true. This creates a gap where directory contents can be enumerated
  without approval.
- **Approval prompts hide attachments:** `get_approval_description` for `_agent_*` and
  `worker_call` does not include attachment details, so the approval prompt omits which files
  are being shared.
- **Docstring mismatch:** `FileSystemToolset` docstring mentions `glob_files`, but the tool is
  actually named `list_files`, which can confuse users and docs.
- **Unused cache:** `_worker_descriptions` is populated but never used, adding dead state
  without payoff.
- **Misleading comment in shell approval:** `ShellToolset.needs_approval` implies metacharacter
  blocking occurs during parsing; the actual block happens in `execute_shell`, so the comment
  can mislead readers about where the rejection originates.

## Open Questions
- Should `worker_call` be constrained by the same allowlist as `_agent_*`, or is it intended
  as an unrestricted escape hatch?
- Should `list_files` be treated as a read operation for `read_approval`?
- Is per-tool approval for custom tools meant to live in `toolsets.custom` or `_approval_config`?
