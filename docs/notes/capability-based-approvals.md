# Approval System Design

## Why Isolation, Not In-Process Security

In-process, library-based security techniques cannot guarantee protection against active attacks. An adversarial or compromised LLM will always find ways to breach sandboxing that runs in the same process—through prompt injection, tool misuse, or exploiting the inherent trust the harness places in tool outputs. We do not attempt to solve this problem at the library level.

**The harness must run in an isolated environment** (VM or container). This is the security boundary.

However, isolation cannot be complete. We want useful work out of that environment. This means controlled channels must exist to extract results—for example, `git push` initiated from the host system pulling committed work, or explicit file transfers. The key constraint: the LLM inside the sandbox cannot autonomously push data out. The host decides when to pull.

## What Approvals Are For

Once running in isolation, approvals serve as a **UI feature**, not a security boundary:

1. **Visibility** — the user sees what the LLM is doing
2. **Guard against LLM mistakes** — typos, wrong files, misunderstood instructions

Approvals do not protect against a determined attacker. They protect against an LLM that misunderstands your intent or makes errors.

## Pragmatic Reality

Everyone accepts that prompt injection cannot be fully prevented and that LLMs with tools should run in isolated environments. But adoption of isolation is slow—setting up VMs or containers adds friction. In practice, many users run harnesses directly on their machines.

We design for isolation as the security boundary, but we accept that approvals will sometimes be treated as a security mechanism. The system should work reasonably in both cases: approvals provide real value as a speed bump even without isolation, just not a guarantee.

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

Tools don't make approval decisions. They declare facts. The runtime holds a single policy that interprets those facts. One place decides, one place to understand, one place to test.

## Capability Granularity

Start coarse to avoid prompt overload:
- `fs.read`, `fs.write`, `fs.delete`
- `net.egress`
- `proc.exec`
- `data.user`, `secrets.access`

Scopes (path-based targeting like `fs.write:/workspace/**`) and parameterized capabilities can wait for v2.

## Composition Model

For composite tools:

1. Composite tool preflights → produces union plan of all capabilities needed
2. Harness decides once based on the plan
3. Harness executes with an approved budget
4. Nested calls must stay within budget or trigger new prompt

## Grant Lifetime

Per-session caching: once a user approves a capability, don't prompt again for the same capability in that session. This is a pragmatic UX choice—there's no theoretical basis that n good edits predict the next one will be safe. But all harnesses offer this, and users expect it. Easy to clear if needed.

## Tool Declarations

Tools declare capabilities, not approval requirements:

```python
ToolDeclaration(
    tool_id="fs.write_text",
    capabilities=("fs.write",),
)
```

Session policy determines prompt level based on capability matching.

Prefer narrow tools (`run_tests`, `git_status`) over raw shell—capabilities are meaningful when tools are specific.

## Session Policy Examples

**Autonomous (isolated sandbox)**:
- Allow read/write/exec
- Deny network egress

**Supervised**:
- Allow reads
- Approve writes, deletes, and network

## Open Questions

- Capability taxonomy: minimal stable set and naming conventions
- UI: raw capability names vs human-readable mapping
- Auto-checkpoint frequency for long-running sessions
- How isolation profile is detected (manifest, CLI flag, runtime default)
