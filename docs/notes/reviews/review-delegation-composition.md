# Delegation and Worker Composition Review

## Context
Review of delegation toolset, worker bootstrapper, and worker composition patterns (including tests/docs/examples).

## Findings
- Delegation collision checks cover filesystem/shell/custom tool names but ignore server-side tools (web_search, web_fetch, code_execution, image_generation). A worker named `web_search` could collide with provider tools without detection.
- `DelegationToolset.worker_create` assumes `WorkerContext.creation_defaults` is populated; when contexts are built outside the runtime helper, the tool can fail at runtime (same root cause as core review).

## Analysis
- Name collisions against provider tools are ambiguous and can cause the LLM to call the wrong tool or fail with confusing errors. This is also a discoverability problem: a worker name that masks a built-in tool makes the toolset surface inconsistent.
- The `creation_defaults` assumption is an integration risk and aligns with the core schema review: external or test callers can trigger a runtime error in the delegation path.

## Possible Fixes
- For server-side tool collisions:
  - Add known provider tool names to the reserved-name set, or
  - Introduce a worker tool prefix (e.g., `worker:<name>` or `_agent_<name>`) to avoid collisions entirely.
  - Alternatively, load the provider tool names from the model/tool registry at runtime to avoid hardcoding.
- For `creation_defaults`:
  - Make it required on `WorkerContext`, or
  - Use a safe default in `worker_create` when missing and surface a clear warning.

## Recommendations
1. Add provider tool names to the reserved list as a short-term safety net.
2. Consider a prefixed worker tool namespace to remove collision risk entirely (no backcompat constraints).
3. Align `creation_defaults` handling with the core schema fix to avoid runtime failures.

## Open Questions
- Should server-side tool names be added to the reserved-name collision set?
- Should delegation tools guard against missing `creation_defaults` (or assert earlier)?

## Conclusion
Collision handling and `creation_defaults` safety are the main risks. A short-term reserved-name list plus a longer-term prefixed namespace would make delegation behavior deterministic and easier to reason about.
