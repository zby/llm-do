# Capability-Based Approvals (Spec)

## Context
The current approval system allows toolsets to make approval decisions via
`SupportsNeedsApproval`. This mixes description and decision: tools know what
happened *and* decide how it should be treated. In llm-do we want the opposite
separation: tools describe facts, the runtime decides. This spec proposes an
optional capability-based approval path for our deps runtime (and a future
upstream proposal) that preserves existing behavior but enables policy to live
in one place.

## Goals
- Keep toolsets focused on describing what a call **is** (capabilities).
- Centralize approval decisions in a policy function/config.
- Avoid breaking existing toolsets or the `ApprovalToolset` API.
- Allow per-call capabilities (dependent on tool args).
- Allow host/runtime policy to vary by environment.

## Non-goals
- Deprecate `SupportsNeedsApproval` or require capability support.
- Define a global capability taxonomy in this doc.
- Implement caching or persistence of approvals (caller concern).

## Proposed API (Additive)

### New protocol
```python
@runtime_checkable
class SupportsCapabilities(Protocol):
    def get_capabilities(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[Any],
        config: ApprovalConfig,
    ) -> set[str] | Sequence[str] | Awaitable[set[str] | Sequence[str]]:
        ...
```

Notes:
- Per-call, arg-dependent.
- Should be fast and side-effect free.
- Returns descriptive labels only (no approval decisions encoded).

### Optional wrapper or policy helper
Provide a new wrapper or helper that **evaluates approvals from capabilities**.
This should be separate from `ApprovalToolset` to avoid changing semantics.

Two possible shapes:

**A. `CapabilityPolicyToolset` (wrapper)**
- Wraps an inner toolset and an `approval_callback` like `ApprovalToolset`.
- Uses `get_capabilities()` (if available) + config to decide `ApprovalResult`.
- If `SupportsCapabilities` is absent, falls back to config-only policy.

**B. `capability_policy` helper (composable)**
- Exposes a function that returns `ApprovalResult` given tool name, args, caps.
- Lets callers compose with existing `ApprovalToolset` (explicitly or in a
  custom wrapper).

Either shape is compatible with existing code; (A) is easier to adopt.

## Policy Evaluation

### Inputs
- `caps`: set of capability labels for a given call.
- `approval_config`: per-tool config (existing type).
- `capability_rules`: mapping from capability -> decision.
- `capability_default`: default decision for unknown capabilities.

### Decision rules (reference)
1. If per-tool config explicitly `blocked` or `pre_approved`, honor it.
2. If any capability is `blocked` by rules, return `blocked`.
3. If any capability is `needs_approval`, return `needs_approval`.
4. If any capability is `pre_approved`, return `pre_approved`.
5. Fallback to `needs_approval_from_config` (secure-by-default).

Rationale: capability rules act as a single centralized policy. Explicit per-tool
config remains as an override mechanism for host environments.

## Capability Sources
Policy wrapper should support multiple sources (union):
- Toolset `get_capabilities(...)` (preferred).
- Static per-tool capabilities in config (optional):
  ```python
  approval_config = {
      "shell": {"capabilities": ["proc.exec"]},
  }
  ```
- Optional `capability_map` for legacy toolsets or glue code.

## Compatibility & Migration
- Existing `ApprovalToolset` and `SupportsNeedsApproval` remain unchanged.
- Capability policy is opt-in and can be introduced per-call.
- Toolsets can add `get_capabilities` incrementally without breaking callers.

## Trade-offs
- **Pros:** single policy layer, easier to audit, fewer toolset forks.
- **Cons:** capability taxonomy may fragment across apps; requires policy wiring.
- **Risk:** developers might encode decisions as capabilities; should be
  discouraged via docs and naming guidance.

## Open Questions
- Should capability policy live inside `ApprovalToolset` or as a separate
  wrapper to avoid changing semantics?
- Should we define a minimal capability vocabulary (e.g., `fs.write`)?
- How to present capabilities to users (raw labels vs. UI mapping)?
- Should capability rules support pattern matching or parameterization?

## Example
```python
from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalRequest

capability_rules = {
    "proc.exec.unlisted": "blocked",
    "proc.exec": "needs_approval",
}

def approve_all(_: ApprovalRequest) -> ApprovalDecision:
    return ApprovalDecision(approved=True)

# Wrap toolsets with capability-aware approval (wrapper or helper)
```
