---
description: Periodic review findings for toolsets.
---

# Toolsets Review

## Context
Review of toolsets for bugs, inconsistencies, and overengineering.

## Findings
- Toolset API shape is consistent across built-ins: `get_tools()` returns a
  `ToolsetTool`, execution is via `call_tool()`, and approval policy is expressed
  via `needs_approval()` + `get_approval_description()`. (`llm_do/toolsets/filesystem.py`,
  `llm_do/toolsets/shell/toolset.py`)
- Shell rule matching is tokenized against parsed args, avoiding prefix
  overmatches (e.g., `git` vs `gitx`), but it assumes each rule is a dict; passing
  `ShellRule` objects or malformed items raises attribute errors at runtime.
  (`llm_do/toolsets/shell/execution.py`)
- `shell_readonly` pre-approves `find`, which can execute arbitrary commands via
  `-exec`/`-execdir` or delete files via `-delete` without any approval prompt,
  undermining the "readonly" expectation. (`llm_do/toolsets/builtins.py`)
- Built-in toolsets use `TypeAdapter(dict[str, Any])` validators, so required
  JSON schema fields are not enforced and missing args surface as `KeyError`
  inside `call_tool()`. (`llm_do/toolsets/filesystem.py`,
  `llm_do/toolsets/shell/toolset.py`, `llm_do/toolsets/attachments.py`)
- Shell config models (`ShellRule`, `ShellDefault`) are defined but unused; tool
  configs are accepted as raw dicts and validation errors surface at runtime.
  (`llm_do/toolsets/shell/types.py`, `llm_do/toolsets/shell/toolset.py`)

## Open Questions
- Should `shell_readonly` treat `find` as approval-required (or explicitly block
  `-exec`/`-delete`) to preserve "readonly" expectations?
- Do we want to validate shell toolset config via `ShellRule`/`ShellDefault`
  models to fail fast on malformed YAML?
- Should built-in toolsets use typed pydantic models for tool args so schema
  requirements are enforced by the validator?

## Conclusion
Core toolsets are consistent, but the biggest correctness gap is the
`shell_readonly` whitelist allowing `find` to execute or delete files without
approval. Tool arg validation and shell config validation are the next cleanup
targets to avoid silent runtime failures.

## Review 2026-02-01

### Findings
- **Shell metacharacter blocking is only enforced in approval path:** `ShellToolset.call_tool()` executes `execute_shell()` without calling `check_metacharacters()`. If a toolset is used without the approval wrapper, blocked metacharacters can run. Add a defense-in-depth check in `call_tool` or `execute_shell`. (`llm_do/toolsets/shell/toolset.py`, `llm_do/toolsets/shell/execution.py`)
- **Shell rules still accept raw dicts:** `ShellRule`/`ShellDefault` models exist but config is unvalidated; malformed rule entries will surface as runtime attribute errors. (`llm_do/toolsets/shell/types.py`, `llm_do/toolsets/shell/toolset.py`, `llm_do/toolsets/shell/execution.py`)

### Resolved Since Prior Review
- **`shell_readonly` now requires approval for dangerous `find` flags:** built-in rules use `approval_required_if_args` for `-exec`, `-execdir`, and `-delete`. (`llm_do/toolsets/builtins.py`, `llm_do/toolsets/shell/execution.py`)
- **Tool arg validation uses typed schemas:** toolsets now validate args with Pydantic models via `DictValidator`. (`llm_do/toolsets/filesystem.py`, `llm_do/toolsets/shell/toolset.py`)

### Open Questions
- Should `execute_shell` always enforce metacharacter blocking even when approval is disabled?
- Should toolset config be validated at instantiation (using `ShellRule`/`ShellDefault`) to fail fast on invalid YAML?

### Conclusion
Shell safety still relies on the approval wrapper for enforcement; add defense-in-depth and config validation to tighten the toolset boundary.
