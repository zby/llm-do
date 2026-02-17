---
description: Capability-based approval system design for tool execution control
areas: ["[[index]]"]
status: current
---

# Approval System Design

Since [[approvals-guard-against-llm-mistakes-not-active-attacks]], the approval system can be designed for usability rather than security. Capabilities are the mechanism.

## Risk Model: Uncommitted Work

The harm from LLM mistakes depends on:

1. **How much uncommitted work exists** in the isolated environment. Past work that has been pulled to a safe location (where the LLM cannot automatically overwrite it) is not at risk.

2. **User interaction preference**:
   - **Fully automated**: user launches a task, checks results later (possibly reviewing with another LLM). Approvals may be disabled or minimal.
   - **Interactive**: user works alongside the LLM, approving significant actions. Higher visibility, lower batch risk.

The user chooses their risk tolerance. The system should support both modes.

## Why Capability-Based Approvals

A common pattern for tool approval has two sources of input:

1. **Tools know what they do** — a file-write tool knows it modifies disk, a shell tool knows it runs arbitrary commands
2. **Runtime knows the environment** — is this isolated? What's the user's risk tolerance?

The naive approach: tools return "needs approval: yes/no" and the runtime also has policies about what needs approval. Then you reconcile them somehow.

This leads to complexity:
- Each tool implements its own reconciliation logic
- Some tools check global policy first, then apply local rules; others do the reverse
- Priority between tool decisions and runtime overrides becomes unclear
- Adding a new policy dimension (e.g., "attachments require approval") means touching every toolset

**Capabilities fix this by separating description from decision:**

- **Tools describe** — return required capabilities per call (`fs.write`, `net.egress`)
- **Runtime decides** — maps capabilities to approval levels based on environment policy

Tools don't make approval decisions. They declare facts. The runtime holds a single policy that interprets those facts. One place decides, one place to understand, one place to test. This separation also means that [[dynamic-agents-runtime-design]] requires no special-case approval logic — dynamically created agents declare capabilities identically to static ones, and the runtime evaluates them through the same policy.

## Capability Granularity

Start coarse to avoid prompt overload:
- `fs.read`, `fs.write`, `fs.delete`
- `net.egress`
- `proc.exec`
- `data.user`, `secrets.access`

Scopes (path-based targeting like `fs.write:/workspace/**`) and parameterized capabilities can wait for v2. [[preapproved-capability-scopes]] explores what that v2 looks like — path-scoped rules that refine these coarse capabilities into fine-grained allow/prompt/deny policies.

## Composition Model

For composite tools:

1. Composite tool preflights → produces union plan of all capabilities needed
2. Harness decides once based on the plan
3. Harness executes with an approved budget
4. Nested calls must stay within budget or trigger new prompt

## Grant Lifetime

Per-session caching: once a user approves a capability, don't prompt again for the same capability in that session. This is a pragmatic UX choice — there's no theoretical basis that n good edits predict the next one will be safe. But all harnesses offer this, and users expect it. Easy to clear if needed. The [[ui-event-stream-blocking-approvals]] broker design implements this via `cache_key` and `remember` semantics on the approval response.

## Tool Declarations

Tools declare capabilities, not approval requirements:

```python
ToolDeclaration(
    tool_id="fs.write_text",
    capabilities=("fs.write",),
)
```

Session policy determines prompt level based on capability matching.

Prefer narrow tools (`run_tests`, `git_status`) over raw shell — capabilities are meaningful when tools are specific. The [[git-integration-research]] proposals illustrate this: a dedicated `git_status` tool can declare `git.read`, while a raw shell command requires the broader `proc.exec`.

## Session Policy Examples

**Autonomous (isolated sandbox)** (when [[container-security-boundary]] provides isolation):
- Allow read/write/exec
- Deny network egress

**Supervised**:
- Allow reads
- Approve writes, deletes, and network

The [[execution-modes-user-stories]] approval scenarios (1-11) concretize these policies across headless automation, interactive chat, and nested delegation.

## Open Questions

- Capability taxonomy: minimal stable set and naming conventions
- UI: raw capability names vs human-readable mapping
- Auto-checkpoint frequency for long-running sessions
- How isolation profile is detected (manifest, CLI flag, runtime default)

---

Relevant Notes:
- [[approvals-guard-against-llm-mistakes-not-active-attacks]] — grounds: establishes that approvals are a UX feature, freeing capability-based design to optimize for usability rather than security
- [[container-security-boundary]] — enables: containers provide the actual security boundary that makes it safe to design capabilities for usability
- [[preapproved-capability-scopes]] — extends: adds path-scoped rules to the coarse capability taxonomy defined here
- [[ui-event-stream-blocking-approvals]] — implements: the approval broker provides the runtime mechanism (cache_key, remember, timeout) for capability grant lifetime
- [[approval-override-rationale]] — supersedes: capability-based policy replaces per-agent overrides with a single policy evaluating declared capabilities
- [[dynamic-agents-runtime-design]] — enables: dynamic agents declare capabilities and are evaluated identically to static agents, requiring no special-case logic
- [[execution-modes-user-stories]] — example: approval scenarios 1-11 concretize capability policies across headless, interactive, and nested delegation modes
- [[llm-do-vs-pydanticai-runtime]] — extends: the "syscall interception" computational model frames tool calls as capability-checked interception points
- [[pure-dynamic-tools]] — example: RestrictedPython sandbox with only `call_agent` is a degenerate case of capability-based policy — one declared capability, always allowed
- [[git-integration-research]] — example: proposed git toolset shows how narrow tools map to specific capability declarations (git.read, git.write, git.push)

Topics:
- [[index]]
