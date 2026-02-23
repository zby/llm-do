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

## 2026-02-09 Review
- Builtin toolset construction has nested closures (`filesystem_factory`, `shell_factory`, `_per_run_toolset`) that can be flattened into a small table-driven builder.
- Filesystem config generation (`cwd` vs `project`) is symmetric; a data-driven config loop would reduce near-duplicate declarations.
- Shell readonly/file_ops rules live as inline dict lists; if reused by docs/tests, centralizing as typed rule objects can reduce drift.
