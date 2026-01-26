# Notes

Working documents for exploration, design thinking, and capturing insights.

## Purpose

1. **Exploration** - Research alternatives, analyze tradeoffs, investigate bugs
2. **Offloading** - Complex thinking that doesn't fit in a commit message or code comment
3. **Future reference** - Insights that might be useful later, even if not acted on now

## Usage

- **Creating**: Add to `docs/notes/` when exploring something non-trivial
- **Archiving**: Move to `archive/` when resolved, implemented, or no longer relevant (archived notes are kept as-is)
- **Referencing**: Link from AGENTS.md or tasks when the note informs decisions

## Subdirectories

- `archive/` — resolved or superseded notes (immutable after archiving)
- `agent-learnings/` — staging area for agent-discovered insights (see its README)
- `meta/` — upstream proposals and cross-project concerns
- `research/` — external research analysis and literature review
- `reviews/` — code review notes and audits

## Note Template

```markdown
# Topic Name

## Context
Why this exploration matters. What prompted it.

## Findings
What was learned, discovered, or designed.

## Open Questions
- Unresolved decisions
- Things that need more investigation
- Tradeoffs not yet decided

## Conclusion
(Add when resolved) What was decided and why.
```

## Guidelines

- Notes are for thinking, tasks are for doing
- Include "Open Questions" to mark unresolved points
- Don't let notes become stale — archive or update them
- Permanent decisions belong in AGENTS.md or code, not notes

---

## Index

### Core Design & Architecture
- [Worker Design Rationale](worker-design-rationale.md) — opt-in tools, isolation, typed I/O
- [Compiler Analogy for Worker Scopes](compiler-analogy-worker-scopes.md) — mental model for scoping
- [Pure Python vs MCP Code Mode](pure-python-vs-mcp-codemode.md) — paradigm comparison
- [llm-do vs vanilla PydanticAI](llm-do-vs-pydanticai-runtime.md) — what the runtime adds

### Approval & Security
- [Approval System Design](capability-based-approvals.md) — capability-based model
- [Preapproved Capability Scopes](preapproved-capability-scopes.md) — reducing approval noise
- [Container Security Boundary](container-security-boundary.md) — future direction

### Execution & UI
- [Execution Modes: User Stories](execution-modes-user-stories.md) — TUI, headless, chat
- [Execution Mode Scripting Simplification](execution-mode-scripting-simplification.md)
- [Event-Stream UI with Blocking Approvals](ui-event-stream-blocking-approvals.md)
- [Tool Output Rendering Semantics](tool-output-rendering-semantics.md)

### Runtime Internals
- [Dynamic Workers Runtime Design](dynamic-workers-runtime-design.md) — runtime agent creation
- [Toolset Instantiation Questions](toolset-instantiation-questions.md)
- [CallSite vs CallScope (Tool Lifecycle)](callsite-callscope-tool-lifecycle.md)
- [Unified Entry Function Design](unified-entry-function-design.md)
- [Stabilize Message Capture](stabilize-message-capture.md) — removing private API dependency
- [Tool Result Truncation Metadata](tool-result-truncation.md)

### Future Features (Specs & Research)
- [Library System Specification](library-system-spec.md) — reusable worker libraries
- [Project Mode and Imports](llm-do-project-mode-and-imports.md) — directory-based projects
- [Git Integration Research](git-integration-research.md) — Aider/golem-forge patterns
- [Python Worker Annotation Brainstorm](python-worker-annotation-brainstorm.md)
- [Agent Skills Standard Unification](agent-skills-unification.md)

### Patterns & Examples
- [Recursive Problem Patterns](recursive-problem-patterns.md)
- [Recursive Worker Patterns (Summary)](recursive-patterns-summary.md)

### Research & Analysis (`research/`)
- [Adaptation of Agentic AI (arXiv paper)](research/adaptation-agentic-ai-analysis.md)
- [Type Catalog Review](research/type-catalog-review.md)
- [Experiment: Runtime without Worker class](research/experiment-runtime-without-worker.md)
- [Manifest-Selected Entry Motivation](research/manifest-selected-entry-motivation.md)
