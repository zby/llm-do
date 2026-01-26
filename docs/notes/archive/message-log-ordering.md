# Message Log Ordering Inconsistency

## Context
Investigating why message logs in verbose mode (-vvv) appeared out of order led to changes for incremental logging. There is still an inconsistency between verbose and non-verbose logging behavior.

## Findings
- When message_log_callback is enabled (-vvv), logs are emitted incrementally and reflect chronological message creation.
- When message_log_callback is disabled, logs are captured at the end of a run, which can be out of chronological order across concurrent runs.
- Making incremental logging universal would require managing PydanticAI's capture_run_messages context so nested worker runs do not overwrite each other.

## Open Questions
- Should incremental logging be made the default for all runs, even when message_log_callback is disabled?
- If yes, should we accept a tighter coupling to PydanticAI internals (e.g., _messages_ctx_var) to ensure isolation per worker run?
- Is it acceptable for runtime.message_log to be empty when message_log_callback is disabled, in exchange for simpler code?
