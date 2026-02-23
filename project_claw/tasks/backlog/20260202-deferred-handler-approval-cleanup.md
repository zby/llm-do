# Deferred Handler Approval Cleanup

## Idea
When PydanticAI implements `deferred_handler` (inline deferred tool resolution), remove llm-do’s custom approval wrapping (`pydantic_ai_blocking_approval` + approval toolset wrappers) and switch to native deferred-tool approvals.

## Why
Reduces llm-do internal complexity and aligns approval behavior with upstream PydanticAI. Avoids per-run wrapper stacking and keeps toolset lifecycle closer to PydanticAI semantics.

## Rough Scope
- Detect upstream availability of `deferred_handler` in PydanticAI.
- Replace llm-do approval wrapping with native `requires_approval` / `ApprovalRequiredToolset` usage.
- Remove `pydantic_ai_blocking_approval` integration and wrapper toolsets.
- Update tests and docs to reflect new approval flow.

## Why Not Now
Blocked on PydanticAI implementing `deferred_handler` (see `../pydantic-ai/deferred_handler_proposal.md` / `deferred_handler_implementation_plan.md`).

## Trigger to Activate
Upstream PydanticAI releases `deferred_handler` in a stable version used by llm-do.
