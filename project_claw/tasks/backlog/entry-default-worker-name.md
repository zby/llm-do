# Default Entry Uses Worker Name

## Idea
When `--entry` is omitted and exactly one `.agent` file is provided, run that worker by its `name` (instead of assuming `main`), so users don't need `main.agent`.

## Why
Reduces boilerplate and makes single-worker projects feel more natural when the worker has a descriptive name.

## Rough Scope
- Update entry resolution logic in `llm_do/runtime/cli.py`.
- Adjust docs/examples that currently assume `main` as the default entry.
- Add/update tests for the new default behavior and ambiguity cases.

## Why Not Now
Needs a decision on compatibility and how to handle multi-worker ambiguity.

## Trigger to Activate
Agreement to drop the `main` default in favor of the single-worker-name default.
