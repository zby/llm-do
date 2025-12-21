# Workers as Skills — Brainstorm

## Context

Workers should extend the SKILLS pattern from Claude Code. Goal: workers feel like skills (declarative, discoverable) but support delegation to isolated agent contexts with their own tools.

## Claude Code's Extension Mechanisms

Claude Code has three ways to extend capabilities:

### 1. Slash Commands (User-Invoked Templates)

```markdown
---
allowed-tools: Bash(git:*), Read
description: Review code for best practices
---

Review the code in $1 for security issues.
```

- User types `/command-name [args]`
- Arguments substituted (`$1`, `$ARGUMENTS`)
- Content injected into conversation
- **No isolation** — same agent context

### 2. Skills (Model-Invoked Prompts)

```markdown
---
name: code-reviewer
description: Reviews code for quality and security issues
allowed-tools: Read, Grep, Glob
---

# Code Reviewer
Analyze code for security vulnerabilities...
```

- Model decides autonomously based on `description`
- Invoked via `Skill` tool
- `allowed-tools` **restricts** which tools can be used
- **No isolation** — same agent context

### 3. Sub-Agents (Isolated Delegation)

```markdown
<!-- .claude/agents/code-reviewer.md -->
---
name: code-reviewer
description: Expert code reviewer for quality checks
tools: Read, Grep, Glob
model: sonnet
---

You are a senior code reviewer...
```

- Model delegates based on `description` matching
- **Isolated context** — separate conversation window
- `tools` field — **inherits all by default** (opt-out to restrict)
- Can be resumed with `agentId`

### 4. MCP Servers (Custom Tools)

```bash
claude mcp add --transport http sentry https://mcp.sentry.dev/mcp
```

- Provides new tools (APIs, databases, services)
- Protocol-based (HTTP, SSE, stdio)
- **Not declarative** — requires running server

### Summary: What Each Provides

| Mechanism | New Tools? | Prompt Context? | Isolation? | Tool Model |
|-----------|------------|-----------------|------------|------------|
| Slash commands | No | Yes (template) | No | Parent's |
| Skills | No (restricts) | Yes | No | Opt-out |
| Sub-agents | No | Yes | **Yes** | **Opt-out** |
| MCP servers | Yes | No | No | N/A |

## Sub-Agents vs Workers

Claude Code's sub-agents already provide isolation. So what do workers add?

| Aspect | Sub-Agents | Workers |
|--------|------------|---------|
| Tool model | **Opt-out** (inherit all, restrict some) | **Opt-in** (declare what you need) |
| Delegation | Heuristic (model decides) | Explicit (`worker_call`) |
| File access | Via tools (Read, Bash) | **Via configured tools** |
| Output | Freeform text | **Typed schemas** |
| Dynamic creation | Manual only | `worker_create()` tool |
| Approval | Claude Code permissions | **Explicit approval controller** |

**Workers = Sub-agents + Explicit Tools + Typed I/O**

The philosophical difference:
- Sub-agents: **conversational context management** (inherit by default)
- Workers: **explicit, auditable delegation** (declare what you need)

## Workers: Skills + Isolation + Tools

| Aspect | Skill | Worker |
|--------|-------|--------|
| Invoked by | Model | Model |
| Discovery | Description matching | Description matching |
| File format | Markdown + frontmatter | Markdown + frontmatter |
| Execution | Prompt injection | **New agent context** |
| Tools | Restricts parent's | **Provisions its own** |
| Returns | Nothing | **Typed result** |

**Worker = Skill + Isolation + Own Tools + Typed I/O**

## Worker Definition Format

Same structure as skills, with additions:

```markdown
---
name: code-reviewer
description: Reviews code for quality and security issues
tools:                          # provisions tools (not restricts)
  - Read
  - Grep
  - worker:security-scanner     # can call other workers
parameters:                     # typed input (becomes tool schema)
  file_path: string
  focus_areas: list[string]?
returns: string                 # typed output
---

# Code Reviewer

You are a code reviewer. Analyze the provided code for:
- Security vulnerabilities
- Performance issues
- Code style violations

Focus on the areas specified by the caller.
```

### Shared with Skills

- Markdown with YAML frontmatter
- Directory-based storage
- Description-based discovery
- Markdown body = system prompt

### Added for Workers

- `tools`: provisions tools (vs skill's `allowed-tools` which restricts)
- `parameters`: typed input schema → tool parameters
- `returns`: typed output schema
- Implicit isolation: new agent context

## Workers Need a Tool Protocol

If workers can call other workers:

```yaml
tools:
  - worker:security-scanner   # Worker A calls Worker B
```

Then workers must be callable as tools. This requires a protocol.

**MCP is the standard tool protocol.** Therefore:

**Workers compile to MCP tools.**

```
Workshop loads
  ↓
Worker definitions parsed
  ↓
Each worker → MCP tool
  ↓
Agent sees workers as tools
  ↓
Worker A calls Worker B (via MCP)
```

### Unified Tool Mechanism

```yaml
tools:
  - Read                      # built-in → MCP
  - Grep                      # built-in → MCP
  - mcp:sentry                # external MCP
  - worker:security-scanner   # worker → MCP
```

All tools are MCP. Workers are declarative MCP servers.

## Pragmatic Path

MCP is heavy, but necessary for v1:
- Standard protocol (Claude Code compatibility)
- Enables worker→worker composition
- Can optimize later

**v1**: Workers compile to MCP
**Later**: Lighter internal protocol, MCP only for external

The value is in the **declarative format**, not the protocol. Get the worker definition right; the mechanism can evolve.

## Summary

Workers combine aspects of Claude Code's skills AND sub-agents:

**From Skills:**
- Markdown + YAML frontmatter format
- Description-based discovery
- Declarative definition

**From Sub-Agents:**
- Isolated agent context
- Own conversation window

**Workers Add:**
- **Opt-in tools** (explicit declaration, not inheritance)
- **Typed I/O** (parameters + return schemas)
- **Explicit delegation** (worker_call, not heuristic)
- **MCP as protocol** (for worker→worker composition)

**Worker = Skill format + Sub-agent isolation + Explicit tooling + Typed I/O**

## Open Questions

- Worker→MCP compilation details?
- Performance overhead of MCP for local workers?
- Remote workers (external MCP servers)?
- Dual-mode: same definition as skill OR worker?
