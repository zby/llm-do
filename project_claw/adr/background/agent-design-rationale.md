---
description: Core design decisions for opt-in tools, isolation, and typed I/O
---

# Agent Design Rationale

Captures the core design decisions that shaped llm-do's agent model.

## Claude Code Extension Mechanisms (Reference)

| Mechanism | New Tools? | Prompt Context? | Isolation? | Tool Model |
|-----------|------------|-----------------|------------|------------|
| Slash commands | No | Yes (template) | No | Parent's |
| Skills | No (restricts) | Yes | No | Opt-out |
| Sub-agents | No | Yes | **Yes** | **Opt-out** |
| MCP servers | Yes | No | No | N/A |

## Why llm-do Uses Opt-In Tools

Claude Code sub-agents inherit all tools by default (opt-out model):
```yaml
tools: Read, Grep  # restricts to just these
# omit tools → gets everything
```

llm-do workers must declare what they need (opt-in model):
```yaml
toolsets:
  filesystem: {}  # explicit
  # nothing else → nothing else available
```

**Rationale**: Opt-in is more secure and auditable. You can read a worker definition and know exactly what it can do. The tradeoff is more verbosity, but worker definitions are meant to be reviewed.

## Core Design Principle

> **Worker = Skill format + Sub-agent isolation + Explicit tooling + Typed I/O**

- **From Skills**: Markdown + YAML frontmatter, description-based discovery, declarative
- **From Sub-Agents**: Isolated agent context, own conversation window
- **Workers Add**: Opt-in tools, typed I/O (result_type), explicit delegation
