---
description: Using Docker containers as security boundary for tool execution
---

# Container Security Boundary

**Status**: Concept / Future Direction

This note explores using Docker containers as the security boundary for tool
execution, rather than implementing per-worker sandboxing in code.

## Context

Currently llm-do has no per-worker path sandbox. This note proposes using
containers as the single security mechanism.

## Concept

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

## Why Containers

1. **Single security mechanism** — One battle-tested boundary instead of custom sandbox code
2. **Dual protection** — Guards against both prompt injection and LLM mistakes
3. **Simpler worker definitions** — No sandbox YAML, just toolsets and prompts
4. **Resource control** — CPU, memory, network limits at container level

## What Runs Where

| Component | Location | Why |
|-----------|----------|-----|
| Orchestrator | Host | Needs to manage containers, talk to LLM APIs |
| Approval controller | Host | User interaction, security decisions |
| Tool execution | Container | Untrusted — could be prompt-injected |
| File operations | Container | Same |
| Network calls | Container (restricted) | Prevent data exfiltration |

## Hybrid Approach

Not everything needs isolation:
- **In container**: Shell commands, code execution, file reads/writes
- **On host**: LLM API calls, approval UI, orchestration

This gives security where it matters without overhead for everything.

## Tradeoffs

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

## Open Questions

- How would container mode be enabled? (`--container` flag? Config option?)
- What base image should be used?
- How to handle credentials that tools need (git, SSH, API keys)?
- Should there be a "local" mode that skips containers for trusted workflows?
