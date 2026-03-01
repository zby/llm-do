---
description: Auto-generated directory — run scripts/generate_notes_index.py /home/zby/llm/llm-do/project_claw/adr to rebuild
type: index
---

# Adr Directory

- [ADR-001: Thin Custom Prefix Adapter + OAuth Gating](./001-thin-custom-prefix-adapter-and-oauth-gating.md) *(adr)* — Thin custom-prefix adapter for model resolution with explicit OAuth gating at project level
- [ADR-002: AgentArgs as Public Input Contract](./002-agent-args-as-public-input-contract.md) *(adr)* — AgentArgs as the stable, typed public input contract for agents and tool schemas
- [ADR-003: Opt-In Tool Model for Agents](./003-opt-in-tool-model.md) *(adr)* — Opt-in tool model where agents explicitly declare needed toolsets rather than inheriting all
- [ADR-004: Unified Tool Plane for Agents and Entry Functions](./004-unified-tool-plane.md) *(adr)* — Unified tool plane ensuring identical observable behavior across agents, entry functions, and scripts
- [ADR-005: Runner Harness vs PydanticAI CLAI](./005-runner-harness-vs-clai.md) *(adr)* — Own runner/harness layer for CLI/TUI instead of adopting PydanticAI's clai
- [ADR-006: Runtime Core vs Simpler Runtime](./006-runtime-core-vs-simpler-runtime.md) *(adr)* — Keep runtime core (registry, call context, approval policy) rather than thin wrapper over PydanticAI
- [AgentArgs Rationale](./background/agent-args-rationale.md) — Why llm-do keeps AgentArgs instead of exposing raw prompt parts as the public input type.
- [Agent Design Rationale](./background/agent-design-rationale.md) — Core design decisions for opt-in tools, isolation, and typed I/O
- [Compiler Analogy for Worker Scopes](./background/compiler-analogy-agent-scopes.md) — Compiler/runtime mental model for worker scopes and tool resolution
- [Recursive Worker Patterns (Summary)](./background/recursive-patterns-summary.md) — Summary of recursive worker patterns for context-limited tasks
- [Recursive Problem Patterns for LLM Workers](./background/recursive-problem-patterns.md) — Catalog of 15 problem types benefiting from recursive LLM workers
- [Unified Entry Function Design](./background/unified-entry-function-design.md) — Design for unified tool plane across workers and entry functions
