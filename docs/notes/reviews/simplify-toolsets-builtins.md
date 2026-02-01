# Simplify: toolsets/builtins.py

## Context
Review of built-in toolset spec creation.

## Findings
- `filesystem_factory()` and `shell_factory()` are nested closures that only
  wrap simple configuration. If these factories are used elsewhere, consider
  lifting them to top-level helpers to reduce nested definitions.
- `_filesystem_config()` always returns both read and write approvals; if
  those are constant, consider moving them into the FileSystemToolset default
  config to reduce duplication here.
- `dynamic_agents` toolset is always registered. If it is optional, consider
  gating it on runtime configuration to reduce unused surface.
