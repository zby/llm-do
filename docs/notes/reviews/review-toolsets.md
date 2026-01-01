# Toolsets Review

## Context
Review of toolsets for bugs, inconsistencies, and overengineering.

## Findings
- Toolset API shape is consistent across built-ins: `get_tools()` returns a
  `ToolsetTool`, execution is via `call_tool()`, and approval policy is expressed
  via `needs_approval()` + `get_approval_description()`. (`llm_do/toolsets/filesystem.py`,
  `llm_do/toolsets/shell/toolset.py`)
- Shell toolset approval is “whitelist + optional default”: unmatched commands
  are blocked unless `default` exists, and metacharacter checks are applied for
  consistent UX. Execution uses `subprocess.run(..., shell=False)` for safety.
  (`llm_do/toolsets/shell/toolset.py`, `llm_do/toolsets/shell/execution.py`)
- Shell rule matching is currently a raw string prefix match (`command.startswith(pattern)`),
  which can overmatch binaries (e.g., a pattern `git` matches `gitx ...`) and
  ignores the already-parsed `args` parameter. This makes whitelisting less
  precise than intended. (`llm_do/toolsets/shell/execution.py`)
- Toolset config is mostly unvalidated: the shell toolset defines `ShellRule` /
  `ShellDefault` models but does not use them to validate YAML config, so malformed
  configs may fail at runtime. (`llm_do/toolsets/shell/types.py`)
- `ToolsetBuildContext` supports injected deps (`cwd`, `worker_name`, etc.), but
  for toolsets that accept a `config` parameter, the loader passes only `config`,
  so other `__init__` params like `id`/`max_retries` aren’t configurable from
  worker YAML unless the toolset reads them from `config`. (`llm_do/toolsets/loader.py`,
  `llm_do/toolsets/filesystem.py`, `llm_do/toolsets/shell/toolset.py`)
- Possible duplication: `llm_do/toolsets/builtins.py` exists but the CLI appears
  to use `llm_do/toolsets/loader.py` + class-path aliases; the builtins registry
  may be dead weight. (`llm_do/toolsets/builtins.py`, `llm_do/toolsets/loader.py`,
  `llm_do/runtime/__init__.py`)

## Open Questions
- Should shell rule matching be based on tokenized args (prefix match on
  `shlex.split`) rather than raw string prefix, to avoid overmatching?
- Do we want to validate toolset config via pydantic models (`ShellRule`,
  `ShellDefault`) to fail fast on invalid YAML?
- Should `ToolsetBuildContext` support setting common toolset params (`id`,
  `max_retries`) even when the toolset accepts a `config` dict?
- Can `llm_do/toolsets/builtins.py` be removed, or repurposed as the single
  source of truth for built-in aliases?

## Conclusion
Core toolsets are small and fairly consistent, but the main correctness gap is
shell rule matching precision. Loader/config validation duplication is the next
cleanup target if/when toolset configuration needs to grow.
