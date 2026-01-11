# Ctx Runtime Review

## Context
Review of runtime core (`llm_do/runtime/*`) for bugs, inconsistencies, and overengineering.

## Findings
- **EntryFunction approvals are intentionally skipped:** code entry points are trusted and call tools directly; documentation should make this trust boundary explicit to avoid confusion. (`llm_do/runtime/shared.py`, `llm_do/runtime/deps.py`, `llm_do/runtime/approval.py`)
- **schema_in_ref can re-exec modules:** `resolve_schema_ref()` uses `load_module()` directly, which re-imports the module even if it was already loaded by discovery; this can re-run module side effects and produce duplicate class identities. (`llm_do/runtime/schema_refs.py`, `llm_do/runtime/discovery.py`)
- **Bulk-approve doesn’t cover attachments:** `bulk_approve_toolsets` swaps in a scoped approval callback for main toolsets, but attachment reads still use the unscoped callback, so repeated attachment approvals continue to prompt. (`llm_do/runtime/worker.py`)
- **Max-depth error lacks context:** `Max depth exceeded` does not include worker name or current depth, making cycles harder to debug. (`llm_do/runtime/worker.py`)
- **Message history behavior matches current intent:** top-level runs reuse `message_history`, nested worker calls always start clean (`_should_use_message_history`).

## Open Questions
- Should top-level worker runs reuse `message_history` while nested worker calls always start from a clean history? (Current intent appears “yes”.)
- Are cyclic worker references intended to work beyond max-depth enforcement? If yes, should cycle detection/error reporting live at resolution or runtime?
- Should bulk-approval apply to attachment reads (or should attachments always hard-fail on denial)?

## Conclusion
Ctx runtime is stable, but there are still approval-boundary edge cases (attachment bulk-approve) and schema ref loading can re-exec modules. Clarifying the trusted-code boundary for EntryFunction calls helps avoid confusion in future reviews.
