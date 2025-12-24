# Worker Design Rationale

Consolidated from early brainstorming. Captures key design decisions and future directions.

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

## Security Model: Container Boundary

Current model assumes llm-do runs inside a container. There is no per-worker
path sandbox in code; the container is the security boundary.

### Concept

Instead of per-worker sandbox declarations, use Docker containers as the security boundary:

```
┌─────────────────────────────────────────┐
│  Host (llm-do orchestrator)             │
│  - Approval controller                  │
│  - Model routing                        │
│  - Worker definitions                   │
└────────────────┬────────────────────────┘
                 │
    ┌────────────▼────────────┐
    │  Container (execution)  │
    │  - Mounted workspace    │
    │  - Tool execution       │
    │  - Resource limits      │
    └─────────────────────────┘
```

### Why Containers

1. **Single security mechanism** — One battle-tested boundary instead of custom sandbox code
2. **Dual protection** — Guards against both prompt injection and LLM mistakes
3. **Simpler worker definitions** — No sandbox YAML, just toolsets and prompts
4. **Resource control** — CPU, memory, network limits at container level

### What Runs Where

| Component | Location | Why |
|-----------|----------|-----|
| Orchestrator | Host | Needs to manage containers, talk to LLM APIs |
| Approval controller | Host | User interaction, security decisions |
| Tool execution | Container | Untrusted — could be prompt-injected |
| File operations | Container | Same |
| Network calls | Container (restricted) | Prevent data exfiltration |

### Hybrid Approach

Not everything needs isolation:
- **In container**: Shell commands, code execution, file reads/writes
- **On host**: LLM API calls, approval UI, orchestration

This gives security where it matters without overhead for everything.

### Tradeoffs

**Benefits:**
- Battle-tested isolation (namespaces, cgroups, seccomp)
- Single security boundary to maintain
- Resource limits (CPU, memory, network)
- Reproducible execution environment

**Costs:**
- Container startup latency (mitigate with warm pools)
- Operational complexity (Docker daemon, images)
- Filesystem sync between host and container
- Some tools may need host access (git creds, SSH keys)
