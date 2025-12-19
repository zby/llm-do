# Runtime and CLI Review

## Context
Review of runtime orchestration, agent execution, toolset loading, and async CLI behavior.

## Findings
- CLI help text for `--model` says "Fallback model if worker does not specify one" but runtime precedence is `--model` > worker model > env var. The flag actually overrides, which is inconsistent with help text and can mislead users.
- TUI mode does not reject `--approve-all` and `--strict` when both are set; JSON/headless modes error out. This is inconsistent approval behavior across modes.
- `_run_tui_mode` emits an error mentioning `--tui` even though no `--tui` flag exists. This is stale UX text.
- `_queue_message_callback` and `_queue_message_callback_direct` are identical; the duplication adds maintenance overhead without clear benefit.
- `create_toolset` takes `context` but never uses it; this appears to be unused plumbing in the loader.

## Analysis
- The `--model` help text mismatch is a user-facing bug: it suggests a fallback behavior when the implementation is an override, which can cause surprising model selection.
- Approval flag mismatch between TUI and headless modes leads to unpredictable behavior and undermines trust in CLI safety invariants.
- Stale `--tui` messaging creates confusion because users cannot discover a nonexistent flag.
- Duplicated callbacks and unused parameters increase surface area for bugs and make refactors harder without providing clarity or extension points.

## Possible Fixes
- Update CLI help text to reflect override semantics and precedence ordering.
- Enforce the same mutual exclusivity check for approval flags in TUI mode as in JSON/headless modes.
- Replace stale error text with the actual flag set (or remove the reference entirely).
- Consolidate `_queue_message_callback` and `_queue_message_callback_direct` into a single helper.
- Remove unused `context` parameter from `create_toolset` or start using it (if intended for future hooks).

## Recommendations
1. Align `--model` help text with actual precedence behavior to prevent user confusion.
2. Enforce consistent approval flag validation across all modes.
3. Remove duplicate callbacks and unused parameters to reduce maintenance overhead.

## Open Questions
- Should TUI mode enforce the same mutually-exclusive approval flag rule as JSON/headless?
- Should the `--model` help text be updated to match the actual override semantics?
- Is the duplicate queue callback intended for future divergence, or should it be consolidated?

## Conclusion
Most issues are UX and consistency gaps rather than deep runtime bugs. Tightening CLI messaging and enforcing uniform flag validation will remove confusion, while cleanup of duplicates will simplify future changes.
