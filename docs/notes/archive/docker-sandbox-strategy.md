# Docker for Sandboxing — Strategy Note

## Context

Currently considering complex path-based sandboxes in worker definitions. Alternative: use Docker for real isolation, like Claude Code does.

## Claude Code's Approach

From Anthropic's Dockerfile:

```dockerfile
FROM node:20

# Network isolation
RUN apt-get install -y iptables ipset iproute2

# Non-root user
USER node

# Isolated workspace
WORKDIR /workspace

# Firewall script for network control
COPY init-firewall.sh /usr/local/bin/
```

Key elements:
- **Container boundary** — OS-level isolation
- **Network firewall** — iptables rules limit network access
- **Non-root execution** — limited privileges
- **Workspace isolation** — dedicated directory

## Current llm-do Approach

Workers declare sandbox paths in YAML:

```yaml
sandbox:
  paths:
    input: { root: ./data, mode: ro }
    output: { root: ./results, mode: rw }
```

Problems:
- **Permission theater** — not real isolation, just checks
- **Complex format** — adds fields to worker definition
- **Hard to verify** — does the code actually enforce it?
- **No network control** — can't limit API calls, etc.

## Docker Alternative

Remove sandbox from worker definition. Workshop handles containerization.

**Worker stays simple** (skill-compatible):
```markdown
---
name: code-reviewer
description: Reviews code for quality
allowed-tools: Read, Grep
delegates-to: [security-scanner]
---

You are a code reviewer...
```

**Workshop provides isolation**:
```yaml
workshop:
  name: code-review-workshop

  container:
    image: llm-do-worker:latest
    network: restricted      # firewall rules
    mounts:
      - ./src:/workspace/src:ro
      - ./output:/workspace/output:rw
    resources:
      memory: 2G
      cpu: 1

  workers:
    - code-reviewer
    - security-scanner
```

## Benefits

1. **Real isolation** — OS-level, not permission checks
2. **Simpler workers** — no sandbox declarations
3. **Network control** — firewall can limit API access
4. **Resource limits** — memory, CPU caps
5. **Aligns with Claude Code** — same model
6. **Skills-compatible** — workers stay close to skill format

## Separation of Concerns

| Layer | Responsibility |
|-------|----------------|
| **Worker** | What to do (prompt, tools, delegation) |
| **Workshop** | Where to run (container, mounts, network) |
| **Docker** | How to isolate (OS-level security) |

Workers are portable. Workshops configure deployment.

## Tradeoffs

**Pros**:
- Real security (not permission theater)
- Simpler worker format
- Network isolation possible
- Resource limits possible

**Cons**:
- Docker dependency (not everyone has it)
- Slower startup (container spin-up)
- More infrastructure complexity
- Harder local development?

## Hybrid Approach?

Could support both modes:

```yaml
workshop:
  isolation: docker    # or "process" for no container
```

- **docker**: Full container isolation
- **process**: Run in same process, permission checks only (dev mode)

Workers don't change. Workshop chooses isolation level.

## Implementation Path

1. **Phase 1**: Remove sandbox from worker format
2. **Phase 2**: Add container support to workshop
3. **Phase 3**: Firewall/network policies
4. **Phase 4**: Resource limits

Start simple: workers without sandbox. Add Docker later.

## Open Questions

- Base image: Python? Node? Multi-language?
- How to handle MCP servers in containers?
- Container per worker or per workshop?
- How does this affect local development workflow?
- Can we reuse Claude Code's firewall script?
