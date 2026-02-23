# ADR-003: Opt-In Tool Model for Agents

**Status:** Accepted

**Date:** 2026-02-01

## Context

When designing llm-do's agent model, we needed to decide how agents access tools. Claude Code sub-agents inherit all tools by default (opt-out model), where you explicitly restrict what's available. We needed to choose between this approach and an opt-in model.

See [agent-design-rationale.md](background/agent-design-rationale.md) for the full analysis.

### Claude Code Reference

| Mechanism | New Tools? | Prompt Context? | Isolation? | Tool Model |
|-----------|------------|-----------------|------------|------------|
| Slash commands | No | Yes (template) | No | Parent's |
| Skills | No (restricts) | Yes | No | Opt-out |
| Sub-agents | No | Yes | **Yes** | **Opt-out** |
| MCP servers | Yes | No | No | N/A |

## Decision

Use an **opt-in tool model** where agents must explicitly declare what toolsets they need:

```yaml
# llm-do: explicit declaration required
toolsets:
  - filesystem_project
  - shell_readonly
# nothing else → nothing else available
```

vs Claude Code's opt-out model:

```yaml
# Claude Code: restricts from inherited set
tools: Read, Grep  # restricts to just these
# omit tools → gets everything
```

### Core Design Principle

> **Agent = Skill format + Sub-agent isolation + Explicit tooling + Typed I/O**

- **From Skills**: Markdown + YAML frontmatter, description-based discovery, declarative
- **From Sub-Agents**: Isolated agent context, own conversation window
- **Agents Add**: Opt-in tools, typed I/O (result_type), explicit delegation

## Consequences

**Positive:**
- More secure: agents can only access what they explicitly declare
- Auditable: you can read an agent definition and know exactly what it can do
- Explicit is better than implicit for security-sensitive operations
- Same pattern works for agents and entry functions

**Negative:**
- More verbose: every agent must declare its toolsets
- Requires understanding what toolsets are available
- No "quick start" with all tools available

The tradeoff is acceptable because agent definitions are meant to be reviewed, and security/auditability outweighs convenience.
