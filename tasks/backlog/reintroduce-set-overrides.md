# Reintroduce --set Overrides

## Idea
Reintroduce runtime overrides for worker configuration via a `--set` CLI flag,
targeting `.agent` definitions and mapping to a clear override syntax.

## Why
Overrides were removed when the CLI did not expose `--set`. If users need
runtime tweaking (models, toolsets, entry fields) without editing files, this
provides a fast feedback loop.

## Rough Scope
- Add CLI flag (`--set KEY=VALUE`, repeatable) and help text.
- Restore override parsing/apply helpers (dot paths, JSON literals).
- Wire overrides into worker file parsing and registry build.
- Define target syntax rules and validation (entry vs named worker).
- Update tests for override parsing, registry behavior, and error cases.

## Why Not Now
No CLI support today; adding overrides adds surface area and extra parsing
complexity without current demand.

## Trigger to Activate
Multiple user requests for runtime overrides or recurring manual edits to
worker files just to change model/toolsets.
