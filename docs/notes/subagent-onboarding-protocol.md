---
description: Bidirectional setup conversation before subagent starts work
---

# Subagent Onboarding Protocol

## Context

From [voooooogel's analysis](research/voooooogel-multi-agent-future.md):

> "just like how a human employee isn't assigned their job based on a single-shot email, it's just too difficult to ask a model to reliably spawn a subagent with a single prompt"

Current agent invocation (both static and dynamic) is single-shot: parent provides input, subagent executes. This often fails because:
- Parent doesn't know what context subagent needs
- Subagent can't ask clarifying questions
- Misunderstandings only surface after work is done

This applies to:
- **Dynamic agents**: `agent_create` + `agent_call`
- **Static agents**: calling a pre-defined `.agent` as a tool
- **Entry functions**: orchestration code invoking agents

### Who Does the Onboarding?

Two options:
1. **Caller-initiated**: The calling agent interviews the subagent before delegating
2. **User-initiated**: A human provides context before the agent starts

For the first prototype, **caller-initiated onboarding** is simpler:
- Stays within the agent-to-agent model
- No UI changes needed
- Caller knows what it needs from the subagent

### Reconciling with Unified Agent/Tool Namespace

In llm-do, agents are exposed as tools. An agent `code_reviewer` becomes a tool that can be called. This creates a tension:

- **Tools are synchronous**: call → result
- **Onboarding is conversational**: call → questions → answers → ... → ready → call → result

Options to reconcile:

**A. Onboarding as separate tool**
```
agent_onboard("code_reviewer", context) → OnboardingHandle
call_agent(handle, input) → result
```
The handle carries onboarding context. Regular tool calls bypass onboarding.

**B. Onboarding phase within tool call**
```
code_reviewer(input, onboard=True) → questions (if any)
code_reviewer(input, onboard_answers={...}) → result
```
Tool call returns questions instead of result when onboarding needed.

**C. Onboarding as agent capability**
The agent itself has an `ask_caller` tool it can use during execution:
```
code_reviewer(input)
  → agent runs, calls ask_caller("What format?")
  → returns to caller with question
  → caller answers
  → agent continues
  → result
```

For prototype, **Option A** is cleanest - explicit separation between onboarding and execution, doesn't change existing tool semantics.

## Proposed Design (Prototype)

Focus: **Caller-initiated onboarding with explicit handle**

```python
# Step 1: Start onboarding conversation
handle = await agent_onboard("code_reviewer", context="Review PR #123 for security")
# Subagent asks: "What languages? Any known vulnerabilities to focus on?"

# Step 2: Answer questions (may loop)
handle = await agent_onboard_reply(handle, "Python/JS. Focus on SQL injection.")
# Subagent asks: "Should I check dependencies too?"

handle = await agent_onboard_reply(handle, "Yes, check requirements.txt")
# Subagent signals ready

# Step 3: Execute with full context
result = await call_agent(handle, input=diff)
```

The handle carries:
- Agent identity
- Accumulated Q&A context
- Ready state

### Why This Design

1. **Explicit phases**: Onboarding vs execution are clearly separated
2. **Preserves tool semantics**: Regular `call_agent(name, input)` still works (no onboarding)
3. **Caller controls the loop**: Parent decides when to stop answering
4. **Works for static and dynamic agents**: Handle can wrap either

### Alternative: Filesystem-Mediated (No New Primitives)

For quick prototyping without new tools:

1. Caller writes `task.md` with context
2. Caller calls `agent(input="read task.md, write questions to questions.md")`
3. Caller reads `questions.md`, writes `answers.md`
4. Caller calls `agent(input="read answers.md and do the task")`

Pros: Works today
Cons: Verbose, caller must orchestrate manually

## Implementation

### New Tools

```python
@tool
async def agent_onboard(agent: str, context: str) -> OnboardingHandle:
    """
    Start onboarding conversation with an agent.

    Returns a handle with the agent's first question (if any),
    or ready=True if no questions needed.
    """

@tool
async def agent_onboard_reply(handle: OnboardingHandle, answer: str) -> OnboardingHandle:
    """
    Reply to an agent's onboarding question.

    Returns updated handle with next question or ready=True.
    """

# Existing tool, extended to accept handle
@tool
async def call_agent(agent: str | OnboardingHandle, input: str) -> str:
    """
    Call an agent. If handle from onboarding, includes Q&A context.
    """
```

### OnboardingHandle

```python
@dataclass
class OnboardingHandle:
    agent: str
    conversation: list[tuple[str, str]]  # [(question, answer), ...]
    current_question: str | None
    ready: bool
```

### Internal Flow

1. `agent_onboard` creates a special agent run with `ask_caller` tool injected
2. Agent runs until it either:
   - Calls `ask_caller(question)` → returns handle with question
   - Returns without asking → returns handle with ready=True
3. `agent_onboard_reply` continues the run with the answer
4. `call_agent(handle, input)` runs the agent with onboarding context prepended

### Message Flow

```
Parent                          Subagent (static or dynamic)
  |                                |
  |-- agent_onboard(name, ctx) --->|
  |                                |-- "What format?" (ask_parent)
  |<-- question ------------------|
  |-- "JSON with schema X" ------>|
  |                                |-- "Any constraints?" (ask_parent)
  |<-- question ------------------|
  |-- "Max 10 files" ------------>|
  |                                |-- "Ready" (no more questions)
  |<-- ready ---------------------|
  |                                |
  |-- call_agent(name, input) --->|
  |                                |-- [executes with full context]
  |<-- result --------------------|
```

For dynamic agents, `agent_create` happens before this flow.

### Batch Onboarding (Fork Pattern)

For spawning multiple similar subagents (from voooooogel):

1. Parent spawns ONE subagent
2. That subagent interviews parent about ALL tasks at once
3. Subagent forks into N instances, each with full onboarding context

This avoids N nearly-identical onboarding conversations.

```
agent_create("task_executor", instructions)
agent_onboard(handle, "I have 10 tasks: [list]. Ask me anything.")
  → single comprehensive Q&A session
agent_fork(handle, 10)
  → returns 10 handles, each with onboarding context
for i, h in enumerate(handles):
    agent_call(h, tasks[i])
```

## Open Questions

- How does onboarding context get passed to the agent? (System prompt? First user message?)
- Should there be a max_questions limit to prevent infinite loops?
- How to handle agents that never signal ready?
- Should onboarding be opt-in per agent (declared in .agent file)?
- Can an already-onboarded handle be reused for multiple calls?
- How does this interact with approval policies? (onboarding questions shouldn't need approval)

## Next Steps

1. **Prototype with filesystem approach** - validate the pattern works
2. **Implement `agent_onboard` / `agent_onboard_reply`** - if pattern proves valuable
3. **Consider user-initiated onboarding** - later, needs UI work
4. **Fork support** - separate feature, combines well with batch onboarding

---

Relevant Notes:
- [dynamic-agents-runtime-design](./dynamic-agents-runtime-design.md) — foundation: the `agent_create`/`agent_call` primitives that onboarding extends with a bidirectional setup phase
