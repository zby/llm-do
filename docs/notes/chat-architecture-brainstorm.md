# Chat Architecture Brainstorm

## Context

Planning multi-turn chat support (Task 35). Starting question: how should the CLI load workshops and manage conversations? This led to deeper insights about the relationship between workshops and workers.

## The Core Constraint

**Tool definitions must be present for the LLM to understand conversation history.**

Without tool schemas, the LLM sees tool call/result messages but can't interpret them. This means:
- Tools must be fixed for the duration of a conversation
- Changing tools mid-conversation breaks history comprehension
- If you need different tools, you need a new context

## Solving Tool Changes: Workers Are Sub-Conversations

What if you need different tools mid-conversation? Options:
1. Start a new conversation (lose context)
2. Delegate to something with different tools (preserve context)

**Insight**: Option 2 is just calling a worker. A worker already has:
- Its own agent context
- Its own tools
- Runs a task, returns result to caller

So "sub-conversation with different tools" = "call a worker". No new concept needed. This is how Claude Code handles it (Task tool spawns agents with different contexts).

## Unifying Workshop and Worker

This insight reveals that workshop and worker are almost the same thing:

| Aspect | Worker | Workshop |
|--------|--------|----------|
| Has tools | ✓ | ✓ |
| Can be entered | `worker_call` | `llm-do --workshop` |
| Interaction mode | Single task (usually) | Chat loop |
| Exit condition | Returns result | User quits |

The difference is **interaction mode**, not the fundamental model. Both are "enter a context with specific tools."

### Generalizing Further: Interactive Workers

If workers could also be interactive, the unification is complete:

| Mode | Input Source | Turns |
|------|--------------|-------|
| Classic worker | Parent agent | Single |
| Interactive worker | User (delegated) | Multi |
| Workshop chat | User (direct) | Multi |

This enables: parent delegates to specialist worker that chats with user directly.

**The core abstraction becomes: context + input source + interaction mode**

## The Key Distinction: Declaration vs Provision

So what actually distinguishes workshop from worker?

**Worker declares requirements. Workshop provides capabilities.**

```yaml
# Worker: declares what it needs (abstract)
worker:
  name: file_processor
  parameters:
    input_dir: path
    output_dir: path
  sandbox:
    read: ["${input_dir}"]
    write: ["${output_dir}"]
```

```yaml
# Workshop: provides the actual sandbox (concrete)
workshop:
  sandbox:
    paths:
      input_dir: /data/input
      output_dir: /data/output
    shell: [npm, python]
  workers:
    - file_processor
```

This is **dependency injection for capabilities**:
- Worker = consumer (portable, reusable, declares dependencies)
- Workshop = provider (runtime environment, binds concrete values)

Workers can run in different workshops with different sandbox bindings.

## Worker Types: Pure vs Effectful

Workers are like procedures — can be pure or have side effects:

**Pure worker**: input → output, no side effects
```yaml
worker:
  name: summarizer
  parameters:
    text: string
  returns: string
```

**Effectful worker**: needs declared capabilities
```yaml
worker:
  name: file_processor
  parameters:
    input_dir: path
    output_dir: path
  sandbox:
    read: ["${input_dir}"]
    write: ["${output_dir}"]
```

Paths are parametric — worker declares *what kind* of access, caller provides *where*. This is like effect systems in functional languages or capability-based security.

## Workers as First-Class Tools

Current design: `worker_call` is a generic tool taking worker name as parameter.

Alternative: Each worker becomes a first-class tool with its own schema.

| Approach | Pros | Cons |
|----------|------|------|
| Generic `worker_call` | Simpler, fewer tools | Worker details hidden from LLM |
| First-class tools | LLMs trained on tools, better context | More schema in context |

Leaning toward first-class tools — tool descriptions in schema are better context engineering than instructions.

## The Full Unification

Worker = prompt + tools (where tools can include other workers)

This is recursive. A worker with workers-as-tools is structurally identical to a workshop.

```
Workshop
  └── prompt + tools
        ├── worker A (prompt + tools)
        ├── worker B (prompt + tools)
        └── custom tool X
```

**Workshop is just the root worker** — distinguished only by:
1. Entry point (invoked from CLI, not `worker_call`)
2. Provides concrete sandbox bindings (declaration vs provision)

## Summary

What started as "how do we add chat?" revealed a unified model:

1. **Worker = prompt + tools** — tools can include other workers (recursive)
2. **Workshop = root worker** — entry point that provides sandbox bindings
3. **Tools fixed per conversation** — delegate to workers for different tools
4. **Workers declare, workshops provide** — dependency injection for capabilities
5. **Workers are portable** — same worker, different workshops

## Open Questions

- Workers as first-class tools vs generic `worker_call` — final decision?
- Syntax for parameter references in sandbox declarations (`${param}`)?
- Permission propagation: can caller grant paths they don't have access to?
- How does approval flow work mid-conversation and across worker calls?
- Should chat loop live in CLI or dedicated runner?
