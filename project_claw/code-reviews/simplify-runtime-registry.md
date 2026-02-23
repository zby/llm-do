# Simplify: runtime/registry.py

## Context
Simplification review of `llm_do/runtime/registry.py` and its internal
dependencies (`llm_do/toolsets/*`, `llm_do/runtime/agent_file.py`,
`llm_do/runtime/discovery.py`, `llm_do/runtime/input_model_refs.py`,
`llm_do/runtime/contracts.py`, `llm_do/models.py`).

## Findings
- **Always builds agent toolsets, even if unused**
  - Pattern: unused flexibility / redundant work.
  - `agent_toolsets` are created for every agent regardless of whether any
    agent references them as a toolset.
  - Simplify by building agent toolsets lazily or only when referenced in a
    toolset list.

- **Multi-pass agent file parsing adds indirection**
  - Pattern: over-specified interface.
  - Agent files are parsed into `AgentFileSpec`, then resolved again for
    toolsets/input models in a second pass.
  - Simplify by adding a `build_agent_spec()` helper that returns an
    `AgentSpec` with resolved toolsets/input model in one pass.
  - Tradeoff: slightly more coupling to `resolve_toolset_specs()` and
    `resolve_input_model_ref()` in the helper.

- **Duplicate conflict checks**
  - Pattern: duplicated validation.
  - `reserved_names` enforces uniqueness vs python agents, while
    `_merge_toolsets()` enforces uniqueness across toolsets. Consider a single
    conflict-checking helper to avoid drift between these checks.

- **Manifest file validation duplicates runtime guard**
  - Pattern: redundant validation.
  - `build_registry()` raises if no `agent_files` or `python_files`, but
    `ProjectManifest` already enforces this. If manifest validation is the
    sole entry point, drop the extra guard.

## Open Questions
- Do we want agent toolsets to exist only when explicitly referenced, or should
  every agent always be callable as a tool by default?

## Conclusion
The registry flow is clear but still does some work unconditionally (agent
toolsets, repeated parsing). A small refactor to build agent specs in one pass
and lazily materialize agent toolsets would reduce surface area without
changing behavior.
