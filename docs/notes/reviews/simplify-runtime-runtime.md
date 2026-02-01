# Simplify: runtime/runtime.py

## Context
Review of shared runtime config/state and entry execution.

## Findings
- `UsageCollector` and `MessageAccumulator` duplicate the same thread-safe
  list pattern. A single generic thread-safe list helper would reduce code.
- `_normalize_agent_approval_overrides()` contains repeated mapping extraction
  logic. Consider a small helper on `AgentApprovalConfig` (e.g.,
  `from_mapping()`) to centralize conversion.
- `run_entry()` performs input normalization and display text extraction,
  then immediately passes `input_args` to `entry.run`. If `entry.run` already
  validates input, consider returning only the display text + messages to avoid
  redundant normalization.

## Open Questions
- Do we need thread-safe collectors here, or can we move usage/message
  accumulation to the async loop for simplicity?
