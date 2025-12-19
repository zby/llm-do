# Runtime CLI Consistency

## Idea
Align CLI help text, approval flag behavior, and internal helpers with actual runtime behavior.

## Why
Current inconsistencies cause user confusion and make approval handling appear unreliable across modes.

## Rough Scope
- Update `--model` help text to match override precedence.
- Enforce mutual exclusivity for `--approve-all` and `--strict` in TUI mode.
- Remove or fix stale `--tui` error messaging.
- Consolidate duplicate queue callbacks.
- Remove or use the unused `create_toolset` context parameter.

## Why Not Now
Requires runtime/CLI touchpoints and coordination with broader CLI changes.

## Trigger to Activate
User reports of CLI confusion or a planned CLI behavior pass.
