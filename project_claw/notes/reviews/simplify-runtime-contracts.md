# Simplify: runtime/contracts.py

## Context
Review of runtime type contracts and entry/agent spec helpers.

## Findings
- `FunctionEntry.__post_init__()` and `AgentSpec.__post_init__()` repeat the
  same input_model validation. Extract a shared helper to avoid drift.
- `ModelType` is a TypeAlias for `Model`. If there is no alternative model
  type planned, the alias adds indirection without value.
- `Entry` is a concrete class with attributes but acts like a protocol. A
  `Protocol` (or `ABC` with explicit `@property` definitions) could reduce
  ambiguity and make the contract clearer.

## Open Questions
- Do we want to keep `Entry` as a base class for type checking, or switch to a
  structural `Protocol` and keep concrete types only?

## 2026-02-09 Review
- `CallContextProtocol` includes a broad registry/dynamic-agent surface in addition to core config/frame behavior; splitting into smaller protocols would reduce over-specified interfaces.
- `FunctionEntry` and `AgentSpec` still duplicate `input_model` validation logic.
- `Entry` remains a nominal base class with required attributes; a structural protocol would better match current usage.
