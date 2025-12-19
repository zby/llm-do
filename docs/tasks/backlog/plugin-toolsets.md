# Plugin Toolsets

## Idea

Enable third-party toolsets via full class paths and uniform DI pattern.

## Why

- Extensibility without modifying llm-do core
- Clean separation between built-in and custom toolsets
- Enables ecosystem of reusable toolsets

## Rough Scope

- Workers declare toolsets by full class path (`mycompany.toolsets.DBToolset`)
- Uniform `(config, context)` constructor pattern for all toolsets
- Generic loading in `toolset_loader.py` (no toolset-specific code)
- Add `create()` classmethod to `ApprovalToolset` in `pydantic-ai-blocking-approval`

## Why Not Now

Current built-in toolsets (`filesystem`, `shell`, `delegation`, `custom`) cover most use cases. No concrete demand for third-party toolsets yet.

## Trigger to Activate

Someone needs a toolset that can't be implemented via `tools.py`.
