# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) documenting significant design decisions in llm-do.

## What is an ADR?

An ADR captures the context, decision, and consequences of an architecturally significant choice. They serve as a log of "why" things are built a certain way.

## Format

Each ADR is a markdown file named `NNN-title.md` (e.g., `001-use-pydantic-for-validation.md`).

### Template

```markdown
# ADR-NNN: Title

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXX

**Date:** YYYY-MM-DD

## Context

What is the issue or question? What forces are at play?

## Decision

What is the change being proposed or made?

## Consequences

What are the results? Both positive and negative.
```

## Background Documents

The `background/` subdirectory contains supporting context that informed decisions. These are documents promoted from `docs/notes/` once they become foundational to an ADR.

## Index

- [ADR-001: Thin Custom Prefix Adapter + OAuth Gating](001-thin-custom-prefix-adapter-and-oauth-gating.md)
- [ADR-002: AgentArgs as Public Input Contract](002-agent-args-as-public-input-contract.md)
- [ADR-003: Opt-In Tool Model for Agents](003-opt-in-tool-model.md)
- [ADR-004: Unified Tool Plane for Agents and Entry Functions](004-unified-tool-plane.md)
- [ADR-005: Runner Harness vs PydanticAI CLAI](005-runner-harness-vs-clai.md)
- [ADR-006: Runtime Core vs Simpler Runtime](006-runtime-core-vs-simpler-runtime.md)
