# ADR-002: AgentArgs as Public Input Contract

**Status:** Accepted

**Date:** 2026-02-01

## Context

Agents consume `list[PromptContent]` at execution time, but callers (Python and tool schemas) need a stable, typed input contract. There was a proposal to drop `AgentArgs` and accept only prompt parts directly.

See [agent-args-rationale.md](background/agent-args-rationale.md) for the full analysis.

## Decision

Keep `AgentArgs` as the public, structured input contract. Treat prompt parts as an internal rendering detail produced by `AgentArgs.prompt_messages()`.

### Why AgentArgs?

- **Tool schemas need JSON-friendly structure.** LLM tool calls require a JSON schema. `list[PromptContent]` includes `Attachment`, which is not JSON-serializable. `AgentArgs` gives a clean, explicit schema for tool calls.
- **Validation is explicit and early.** `AgentArgs` allows Pydantic validation of inputs before the agent runs, preventing prompt-level bugs from leaking into runtime behavior.
- **Meaning stays separate from prompt formatting.** `AgentArgs` captures semantic fields (e.g., `topic`, `limit`, `file_path`) while `prompt_messages()` maps them to prompt text/attachments.
- **Schema reuse for documentation and tooling.** The same `AgentArgs` class powers tool-call schemas, runtime normalization, and human-readable input shapes.
- **Forward-compatible with richer prompting.** If prompt structure evolves (roles, system/user partitions, multimodal ordering), the rendering can change without breaking callers.

### Alternatives Considered

1. **Expose prompt parts directly** - Rejected: weak schema, hard to validate, not JSON-friendly.
2. **Introduce a JSON-friendly PromptPart model** - Viable but more complex for LLM tool calls and offers less semantic clarity than `AgentArgs`.

## Consequences

- Callers should prefer `AgentArgs` (or dicts validated against them) for anything beyond trivial `input`/`attachments`.
- Prompt parts remain an internal boundary that agents can change without breaking call sites.
- A default `PromptInput` (`input` + `attachments`) eliminates `input_model=None` paths.
