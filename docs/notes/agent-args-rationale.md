---
description: Why llm-do keeps AgentArgs instead of exposing raw prompt parts as the public input type.
---

# AgentArgs Rationale

## Context
Agents consume `list[PromptContent]` at execution time, but callers (Python and tool schemas) need a stable, typed input contract. There was a proposal to drop `AgentArgs` and accept only prompt parts.

## Decision
Keep `AgentArgs` as the public, structured input contract. Treat prompt parts as an internal rendering detail produced by `AgentArgs.prompt_messages()`.

## Why keep AgentArgs?
- **Tool schemas need JSON‑friendly structure.** LLM tool calls require a JSON schema. `list[PromptContent]` includes `Attachment`, which is not JSON‑serializable. `AgentArgs` gives a clean, explicit schema for tool calls.
- **Validation is explicit and early.** `AgentArgs` allows Pydantic validation of inputs before the agent runs, which prevents prompt‑level bugs from leaking into runtime behavior.
- **Meaning stays separate from prompt formatting.** `AgentArgs` captures semantic fields (e.g., `topic`, `limit`, `file_path`) while `prompt_messages()` maps them to prompt text/attachments. This separation avoids overloading prompt strings as the only contract.
- **Schema reuse for documentation and tooling.** The same `AgentArgs` class powers tool-call schemas, runtime normalization, and human‑readable input shapes.
- **Forward‑compatible with richer prompting.** If prompt structure evolves (roles, system/user partitions, multimodal ordering), the rendering can change without breaking callers.

## Why not expose only prompt parts?
`list[PromptContent]` is the lowest‑level representation. Making it the public contract:
- removes structured validation,
- makes tool schemas brittle or impossible,
- pushes meaning into free‑text prompt strings, and
- locks callers into an internal representation that might change.

## Alternatives considered
1. **Expose prompt parts directly**  
   Rejected: weak schema, hard to validate, not JSON‑friendly.
2. **Introduce a JSON‑friendly PromptPart model**  
   Viable but more complex for LLM tool calls and offers less semantic clarity than `AgentArgs`.

## Consequences
- Callers should prefer `AgentArgs` (or dicts validated against them) for anything beyond trivial `input`/`attachments`.
- Prompt parts remain an internal boundary that agents can change without breaking call sites.

## Open Questions
- Should we introduce a default `AgentArgs` (e.g., `input` + `attachments`) to eliminate `input_model=None` paths?
- Do we need a canonical, JSON‑friendly `PromptPart` model for tool calls that require ordered multimodal content?
