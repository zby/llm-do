# Simplify: toolsets/dynamic_agents.py

## Context
Review of dynamic agent creation/call toolset.

## Findings
- `needs_approval()` duplicates the agent-call approval logic from
  `AgentToolset`. A shared helper would keep approval policy consistent and
  reduce code.
- `_agent_create()` writes the agent file, then re-parses it from disk. Since
  the frontmatter + instructions are already in memory, consider constructing
  `AgentDefinition` directly and only writing the file after validation.
- `_resolve_generated_dir()` duplicates runtime logic for generated agent
  directories. Consider using a shared helper to avoid diverging path rules.

## Open Questions
- Should dynamic agent creation be allowed without writing to disk (in-memory
  agent definitions)? If so, the file parse/write round-trip can be removed.
