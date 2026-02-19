---
description: Two upstream PydanticAI paths could eliminate our ApprovalToolset wrapper stacking — deferred_tool_handler and Traits before_tool_call hooks
areas: [approvals-index, pydanticai-upstream-index]
status: current
last_verified: 2026-02-18
---

# We want to get rid of approval wrapping

Our approval system works by wrapping every toolset in `ApprovalContextToolset` (and optionally `ApprovalDeniedResultToolset`) at call time. This is ~440 lines of wrapping infrastructure across `runtime/approval.py` (186) and `runtime/call.py` (256), plus the external `pydantic-ai-blocking-approval` dependency. The wrapping is the single largest piece of PydanticAI impedance-mismatch code we maintain. It is also the primary driver behind [toolset-state-prevents-treating-pydanticai-agents-as-global](./toolset-state-prevents-treating-pydanticai-agents-as-global.md) — since wrapping must happen before `Agent(toolsets=...)`, llm-do is forced to construct a new Agent per call.

Two upstream PydanticAI proposals could eliminate it. Both are unshipped as of February 2026.

## Path 1: `deferred_tool_handler`

An optional callback on `agent.run()` that handles deferred tool calls (approvals) inline within the agent loop, without returning control to the caller.

**How it eliminates wrapping:** Toolsets use PydanticAI's native `requires_approval` / `ApprovalRequired` raise pattern. The handler receives all deferred tools per LLM response, returns approve/deny decisions. PydanticAI's loop handles execution of approved tools and synthetic denial results. No wrapper layers needed.

**What we keep:** The per-toolset `needs_approval()` / `get_approval_description()` methods stay — they feed into PydanticAI's existing `ApprovalRequired` mechanism. The approval callback factories (`make_tui_approval_callback`, `make_headless_approval_callback`) adapt to produce `DeferredToolResults` instead of `ApprovalDecision`. Session caching logic stays. The [ui-event-stream-blocking-approvals](./ui-event-stream-blocking-approvals.md) broker's `request_approval` / `respond` interface would adapt: the broker produces `DeferredToolResult` instead of `ApprovalDecision`, and the handler-receives-all-deferred-per-response pattern maps naturally to the broker's batch model.

**What we delete:** `ApprovalContextToolset`, `ApprovalDeniedResultToolset`, `_prepare_toolsets_for_run()` wrapping logic, `_unwrap_approval_toolset()`, double-wrap detection, the `pydantic-ai-blocking-approval` package dependency. This also resolves [proposed-toolset-lifecycle-resolution-for-pydanticai](./proposed-toolset-lifecycle-resolution-for-pydanticai.md)'s caveat that "the approval wrapping question remains separate" — once wrapping is gone, PydanticAI's first-class factory pattern (Layer 2) could fully subsume llm-do's per-call Agent construction.

**Type migration required:** Today `needs_approval()` takes `ApprovalConfig` and returns `ApprovalResult` from `pydantic-ai-blocking-approval`. These types are used across 8 files (`filesystem.py`, `shell/toolset.py`, `dynamic_agents.py`, `agent.py`, `runtime/approval.py`, `runtime/call.py`, `ui/runner.py`, `__init__.py`). When the package is deleted, these types must be replaced. The [type-catalog-review](./type-catalog-review.md) documents the current duplication (`ApprovalMode` in multiple places, `AgentApprovalOverride` vs `AgentApprovalConfig` shape duplication) that this migration should also clean up. Two options:

- **Adopt PydanticAI's native types.** If `deferred_tool_handler` ships with its own approval result types (likely `ApprovalRequired` exception + result protocol), our toolsets switch to those. The `needs_approval()` method signature changes to return whatever PydanticAI expects.
- **Inline the types we actually use.** `ApprovalResult` is a small dataclass (pre_approved/needs_approval/blocked). `ApprovalConfig` is a dict. `ApprovalDecision` is approved + note + remember. We could vendor the ~50 lines of type definitions we actually depend on, or (preferably) upstream them into PydanticAI core since they're needed for any approval pattern.

The `__init__.py` re-exports (`ApprovalBlocked`, `ApprovalCallback`, `ApprovalDecision`, `ApprovalDenied`, `ApprovalError`, `ApprovalRequest`, `ApprovalResult`, `ApprovalToolset`) are part of our public API. Removing them is a breaking change that must be handled in a major version bump or with deprecation re-exports.

**Status:** We wrote a detailed proposal draft (see [blocking_approvals](./meta/blocking_approvals.md)). Blocked on PydanticAI implementing `deferred_tool_handler`. Related upstream issues: [#3274](https://github.com/pydantic/pydantic-ai/issues/3274), [#3488](https://github.com/pydantic/pydantic-ai/issues/3488).

## Path 2: Traits `before_tool_call` hooks

The Traits API proposal ([PR #4233](https://github.com/pydantic/pydantic-ai/pull/4233)) includes lifecycle hooks. A `before_tool_call` hook intercepts every tool call and can block it (return `False`) or modify args (return `dict`).

**How it eliminates wrapping:** An `ApprovalTrait` implements `before_tool_call` to check capabilities and prompt the user. No toolset wrapping at all — the hook sits in the agent loop itself, cross-cutting all toolsets.

**What we keep:** Same as Path 1 — the per-toolset `needs_approval()` declarations, callback factories, session caching. Same type migration requirement as Path 1.

**What we delete:** Same as Path 1 — all wrapping infrastructure and the external dependency.

**Critical requirement: runtime deps in hooks.** For this path to work for us, `before_tool_call` must receive `RunContext[Deps]` — our approval logic needs access to the approval callback, session cache, capability policy, and other runtime state injected via deps. Without deps, the hook can't make policy decisions. The current proposal signature includes `ctx: RunContext[AgentDepsT]`, which would work.

**Denied-call UX mapping.** Today `ApprovalDeniedResultToolset` catches `PermissionError` from denied calls and returns a structured payload `{"error": str, "tool_name": str, "error_type": "permission"}` instead of raising. This is toggled by `return_permission_errors` in `RuntimeConfig` and consumed by the TUI (`ui/runner.py`) and CLI (`cli/main.py`). A `before_tool_call` hook that returns `False` must produce an equivalent tool result — PydanticAI needs to either: (a) return a configurable denial payload as the tool result when `before_tool_call` blocks, or (b) let the hook return a custom result dict instead of a bare `False`. Without this, the LLM sees a different signal on denial (possibly an exception or missing result) and the TUI loses the structured error display.

**Status:** The Traits API is in research/design phase. See [pydanticai-traits-api-analysis](./pydanticai-traits-api-analysis.md) for our analysis of the proposal and its implications for llm-do.

## Comparison

| Dimension | `deferred_tool_handler` | Traits `before_tool_call` |
|-----------|------------------------|---------------------------|
| Scope | Focused: approval/deferred tools only | Broad: any cross-cutting tool behavior |
| Implementation size | Small upstream change (agent loop) | Large upstream change (full Traits system) |
| Likely timeline | Nearer — addresses existing issues | Further — requires entire Traits API |
| Our migration effort | Moderate — rewrite callback bridge | Moderate — rewrite as Trait class |
| Composability | Limited — one handler per run | Rich — multiple traits compose |
| Capability-based policy fit | Works but policy lives in our handler | Natural fit — trait declares, policy decides |
| Other benefits for us | None beyond approvals | Could replace lifecycle scaffolding (`CallScope`, depth tracking, toolset teardown) |

## Assessment

**Path 1 arrives first and solves the immediate pain.** The `deferred_tool_handler` is a targeted addition that could ship independently. We should be ready to adopt it as soon as it lands.

**Path 2 is the better long-term architecture.** Traits hooks eliminate wrapping *and* could subsume our entire `CallScope`/`CallFrame` lifecycle layer. But it's a larger upstream effort and may take longer to stabilize.

**They're not mutually exclusive.** If `deferred_tool_handler` ships first, we migrate to it. When Traits ships later, we migrate again from handler to trait — a smaller delta since the wrapping is already gone.

## Open Questions

- Would PydanticAI accept `deferred_tool_handler` as a standalone feature, or would they prefer to wait for Traits to subsume it?
- If Traits ships without `RunContext[Deps]` in hooks, can we work around it via closure capture, or is that a dealbreaker?
- Could we prototype the Traits path locally (our own `ApprovalTrait` using `before_tool_call`) even before upstream ships, to validate the design?
- Must `return_permission_errors` semantics be preserved post-migration, or can we simplify to always-return (never-raise) for denied calls?
- Are the `__init__.py` re-exports (`ApprovalBlocked`, `ApprovalCallback`, etc.) used by downstream consumers? If so, removal needs deprecation warnings before a breaking change.
- Should the replacement types live in llm-do (vendored) or be proposed as additions to PydanticAI core?

---

Relevant Notes:
- [blocking_approvals](./meta/blocking_approvals.md) — detailed `deferred_tool_handler` proposal draft we authored
- [pydanticai-traits-api-analysis](./pydanticai-traits-api-analysis.md) — analysis of the Traits API proposal and its implications for approval wrapping and lifecycle scaffolding
- [capability-based-approvals](./capability-based-approvals.md) — our long-term direction for approval policy (tools declare capabilities, runtime decides)
- [approvals-guard-against-llm-mistakes-not-active-attacks](./approvals-guard-against-llm-mistakes-not-active-attacks.md) — foundation: approvals are UX, not security
- [stateful-flag-evaluation-against-toolset-spectrum](./stateful-flag-evaluation-against-toolset-spectrum.md) — eliminating wrapping is a prerequisite for the `stateful` flag to work cleanly in frameworks that currently wrap toolsets
- [toolset-state-prevents-treating-pydanticai-agents-as-global](./toolset-state-prevents-treating-pydanticai-agents-as-global.md) — enables: eliminating wrapping removes the primary reason for per-call Agent construction, since toolsets no longer need wrapping before `Agent(toolsets=...)`
- [proposed-toolset-lifecycle-resolution-for-pydanticai](./proposed-toolset-lifecycle-resolution-for-pydanticai.md) — enables: once wrapping is gone, PydanticAI's first-class factory pattern (Layer 2) could fully subsume llm-do's per-call construction
- [ui-event-stream-blocking-approvals](./ui-event-stream-blocking-approvals.md) — adapts: the approval broker's callback interface maps to `DeferredToolResult` in Path 1 and `before_tool_call` return values in Path 2
- [type-catalog-review](./type-catalog-review.md) — context: documents the `ApprovalMode` duplication and override shape duplication that the type migration should clean up

Topics:
- [index](./index.md)
- [pydanticai-upstream-index](./pydanticai-upstream-index.md)
