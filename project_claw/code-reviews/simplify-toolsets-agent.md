# Simplify: toolsets/agent.py

## Context
Review of the AgentToolset wrapper that exposes AgentSpec as a tool.

## Findings
- Approval logic for agent calls duplicates the logic in
  `DynamicAgentsToolset.needs_approval()`. Consider a shared helper to compute
  approval decisions for agent calls to keep policy consistent. Done: shared
  helper added in `runtime/approval.py` and used by both toolsets.
- `_messages_from_args()` and `_get_attachment_paths()` re-parse inputs. When
  both approval and description need attachments, consider parsing once and
  passing messages/attachments through to avoid duplicate work.
- `get_tools()` truncates descriptions at 200 chars inline; a shared truncation
  helper (used by UI too) would reduce scattered constants.

## Open Questions
- Do we want agent-call approval policy to live in runtime config instead of
  toolset logic (to reduce duplication across toolsets)?

## 2026-02-09 Review
- `_messages_from_args()` and `_get_attachment_paths()` still re-parse the same payload in approval and description flows; parse once and reuse derived attachments.
- `get_tools()` still truncates description inline with fixed `200` constant; moving shared truncation policy to one UI/runtime formatting helper would reduce duplicated presentation decisions.
- `agent_as_toolset()` always wraps with `DynamicToolset(per_run_step=False)`; if per-run static instance is sufficient, direct toolset construction could remove one indirection layer.
