# Avoid double get_tools pass in WorkerRuntime.call

## Idea
Consolidate tool lookup and available list to avoid a second get_tools pass and ensure consistent snapshots.

## Why
Reduce redundant toolset calls, prevent inconsistent "available" listings, and clarify tool resolution semantics.

## Rough Scope
- Decide lookup semantics (early-return vs full snapshot; failure behavior if later get_tools fails).
- Decide available list format (dedupe/order/toolset IDs).
- Implement single-pass lookup in `llm_do/runtime/deps.py`.
- Add tests for chosen semantics.

## Why Not Now
Runtime behavior is in transition; avoid changes until decisions are settled.

## Trigger to Activate
Agreement on semantics and willingness to modify runtime behavior.
