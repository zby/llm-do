# Workers vs Claude Code Sub-Agents — Brainstorm

## Context

Claude Code has sub-agents that provide isolated delegation. We're designing workers for llm-do. What's the relationship? What do workers add? Should we align more closely?

## Claude Code Sub-Agents

Definition format (`.claude/agents/{name}.md`):

```markdown
---
name: code-reviewer
description: Expert code reviewer for quality checks
tools: Read, Grep, Glob
model: sonnet
permissionMode: default
skills: skill1, skill2
---

You are a senior code reviewer...
```

### Key Properties

| Property | Behavior |
|----------|----------|
| `tools` | **Inherits all if omitted** (opt-out model) |
| `model` | Defaults to sonnet, can specify or "inherit" |
| `description` | Used for **heuristic delegation** — model decides when to use |
| `permissionMode` | Controls how permissions are handled |
| `skills` | Auto-loads specified skills into sub-agent |

### Invocation

- **Heuristic**: Model decides based on description matching task
- **Explicit**: User can request specific sub-agent
- **Resumable**: Can continue previous conversation with `agentId`

### What Sub-Agents Provide

1. **Isolation**: Separate conversation context
2. **Tool restriction**: Can limit tools (but inherits all by default)
3. **Model selection**: Can use different model
4. **Skill composition**: Can load skills into sub-agent

## llm-do Workers (Revised Design)

Definition format (`workers/{name}.worker`):

```yaml
name: code-reviewer
description: Reviews code for quality issues
model: claude-sonnet-4

toolsets:
  filesystem: {}
  delegation:
    allow_workers: [security-scanner]

output_schema_ref: ReviewResult
---

You are a code reviewer...
```

### Key Properties

| Property | Behavior |
|----------|----------|
| `toolsets` | **Explicit declaration** (opt-in model) |
| `allow_workers` | **Explicit allowlist** for delegation |
| `output_schema_ref` | **Typed output** |
| `model` | Inherited from caller if omitted |

### Invocation

- **Explicit**: `worker_call(name, input)` tool
- **Approval-gated**: Goes through approval controller
- **Not resumable**: Each call is fresh context

### Container-Based Isolation (New Direction)

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

**Why containers instead of worker-level sandboxes:**

1. **Single security mechanism** — One battle-tested boundary instead of custom sandbox code
2. **Dual protection** — Guards against both prompt injection and LLM mistakes
3. **Simpler worker definitions** — No sandbox YAML, just toolsets and prompts
4. **Resource control** — CPU, memory, network limits at container level
5. **Reproducibility** — Same environment for all tool execution

## Side-by-Side Comparison

| Aspect | Sub-Agents | Workers |
|--------|------------|---------|
| Format | Markdown + YAML frontmatter | Same |
| Delegation | LLM decides (description) | Same |
| Tools | Opt-out (inherit all) | Opt-in (declare needed) |
| File access | Via tools | Container-mounted workspace |
| Isolation | In-process sandbox | Docker container |
| Output | Freeform | Typed schemas |
| Resumable | Yes | No |
| Approval | Claude Code system | Explicit controller |
| Nested | Yes (sub-agents can spawn) | Yes (allow_workers) |

## What Are the Real Differences?

### 1. Tool Model: Opt-out vs Opt-in

**Sub-agents**: Inherit all tools by default
```yaml
tools: Read, Grep  # restricts to just these
# omit tools → gets everything
```

**Workers**: Must declare what you need
```yaml
toolsets:
  filesystem: {}  # explicit
  # nothing else → nothing else available
```

**Question**: Is opt-in better? More secure, more auditable. But also more verbose.

### 2. File Access: Tools vs Containers

**Sub-agents**: File access via Read/Write/Bash tools
- No path restrictions (beyond what tools allow)
- Same access as parent (unless tools restricted)
- In-process sandbox within Claude Code

**Workers**: Container-mounted workspace
- Workspace directory mounted into container
- All tool execution happens inside container
- No per-worker path declarations needed

**Key insight**: Containers are needed anyway for prompt injection protection. Using them as the isolation boundary also protects against LLM mistakes — two concerns, one mechanism.

### 3. Delegation: Heuristic vs Explicit

**Sub-agents**: Model decides when to delegate based on description
- "I need to review code" → model picks code-reviewer

**Workers**: Caller explicitly invokes
- `worker_call("code-reviewer", {file: "main.py"})`

**Question**: Is explicit better? More predictable. But less autonomous.

### 4. Output: Freeform vs Typed

**Sub-agents**: Return text to parent conversation

**Workers**: Can have typed output schema
```yaml
output_schema_ref: ReviewResult
```

**Question**: Is typing necessary? Better for pipelines. But adds friction.

## Where Should Workers Align with Sub-Agents?

### Candidates for Alignment

1. **Format**: Could use Markdown + frontmatter (like sub-agents/skills)
2. **Resumability**: Could add ability to resume workers
3. **Skill composition**: Could load skills into workers

### Candidates for Divergence

1. **Opt-in tools**: Keep explicit declaration (security)
2. **Container isolation**: Use Docker instead of per-worker sandbox declarations
3. **Typed output**: Keep for pipeline use cases
4. **Explicit delegation**: Keep for predictability

## Strategic Insight: Skills Are Becoming Standard

**Observation**: Skills are being adopted across code assistants. Sub-agents aren't.

Why skills win:
- **Simpler**: Just markdown + frontmatter
- **Portable**: Easy to share, copy, version
- **Understandable**: Non-programmers can read/write them
- **Low commitment**: Try it, delete it if it doesn't work

Why sub-agents don't spread:
- **More complex**: Isolation, tool inheritance, resumption
- **Platform-specific**: Tied to Claude Code's runtime
- **Harder to reason about**: What tools does it have? What can it access?
- **Overkill for most tasks**: Simple prompt injection suffices

**Strategic implication**:

> Extending the skill standard for delegation is easier than establishing a sub-agent standard.

Workers should be: **skills with delegation capability**

Not: sub-agents with explicit tools

## Workers as "Skills That Can Delegate"

What if workers ARE skills, with optional delegation?

```markdown
---
name: code-reviewer
description: Reviews code for quality issues

# Standard skill fields
allowed-tools: Read, Grep, Glob

# Delegation extension
delegates-to:              # NEW: can call these workers
  - security-scanner
  - style-checker
isolation: true            # NEW: runs in own context (default: false = skill mode)
parameters:                # NEW: typed input (optional)
  file_path: string
returns: string            # NEW: typed output (optional)
---

You are a code reviewer...
```

### The Spectrum

```
Skill (standard)
  ↓ add isolation: true
Isolated Skill (like sub-agent)
  ↓ add delegates-to
Worker (can delegate)
  ↓ add parameters/returns
Typed Worker (pipeline-ready)
```

All using the same format. Progressive enhancement.

### Compatibility

- **Pure skill** (no extensions): Works as standard skill
- **With isolation**: Becomes sub-agent-like
- **With delegates-to**: Becomes worker
- **Full spec**: Typed worker for pipelines

One format, multiple modes.

## Why This Wins

1. **Adoption**: Start with skill-compatible format
2. **Migration**: Existing skills work, add delegation later
3. **Simplicity**: Most workers are just skills + one or two fields
4. **Standards**: Contribute back to skill ecosystem

## Revised Design Direction

Don't design workers as "sub-agents with explicit tools".

Design workers as "skills with delegation extensions".

The format is skills. The extensions enable delegation.

## Open Questions

- What's the minimal extension to skills for delegation?
- Should `isolation` be explicit or implied by `delegates-to`?
- Can we propose skill extensions as a standard?
- Container strategy: warm pools vs on-demand? Network policy?

## Container Implementation Considerations

### What runs where

| Component | Location | Why |
|-----------|----------|-----|
| Orchestrator | Host | Needs to manage containers, talk to LLM APIs |
| Approval controller | Host | User interaction, security decisions |
| Tool execution | Container | Untrusted — could be prompt-injected |
| File operations | Container | Same |
| Network calls | Container (restricted) | Prevent data exfiltration |

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

### Hybrid approach

Not everything needs to run in containers:
- **In container**: Shell commands, code execution, file writes
- **On host**: Read-only file access, web fetches, LLM calls

This gives security where it matters without overhead for everything.
