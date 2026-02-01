# Simplify: toolsets/agent.py

## Context
Review of the AgentToolset wrapper that exposes AgentSpec as a tool.

## Findings
- Approval logic for agent calls duplicates the logic in
  `DynamicAgentsToolset.needs_approval()`. Consider a shared helper to compute
  approval decisions for agent calls to keep policy consistent.
- `_messages_from_args()` and `_get_attachment_paths()` re-parse inputs. When
  both approval and description need attachments, consider parsing once and
  passing messages/attachments through to avoid duplicate work.
- `get_tools()` truncates descriptions at 200 chars inline; a shared truncation
  helper (used by UI too) would reduce scattered constants.

## Open Questions
- Do we want agent-call approval policy to live in runtime config instead of
  toolset logic (to reduce duplication across toolsets)?
