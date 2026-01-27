# Notes

Working documents for exploration, design thinking, and capturing insights.

## Purpose

1. **Exploration** - Research alternatives, analyze tradeoffs, investigate bugs
2. **Offloading** - Complex thinking that doesn't fit in a commit message or code comment
3. **Future reference** - Insights that might be useful later, even if not acted on now

## Usage

- **Creating**: Add to `docs/notes/` with YAML frontmatter (see below)
- **Archiving**: Move to `archive/` when resolved or no longer relevant
- **Referencing**: Link from AGENTS.md or tasks when the note informs decisions

## Subdirectories

- `archive/` — resolved or superseded notes (immutable after archiving)
- `agent-learnings/` — staging area for agent-discovered insights
- `meta/` — upstream proposals and cross-project concerns
- `research/` — external research analysis and literature review
- `reviews/` — code review notes and audits

## Frontmatter

All notes should have YAML frontmatter with a description:

```markdown
---
description: One-line summary of what this note covers
---

# Note Title

Content...
```

Regenerate the index: `python scripts/generate_notes_index.py`

## Guidelines

- Notes are for thinking, tasks are for doing
- Include "Open Questions" to mark unresolved points
- Don't let notes become stale — archive or update them
- Permanent decisions belong in AGENTS.md or code, not notes

---

## Index

- [Agent Design Rationale](agent-design-rationale.md) — Core design decisions for opt-in tools, isolation, and typed I/O
- [Agent Skills Standard Unification](agent-skills-unification.md) — Aligning .agent format with Agent Skills standard specification
- [CallSite vs CallScope (Tool Lifecycle)](callsite-callscope-tool-lifecycle.md) — Tool lifecycle management between CallSite and CallScope abstractions
- [Approval System Design](capability-based-approvals.md) — Capability-based approval system design for tool execution control
- [Compiler Analogy for Worker Scopes](compiler-analogy-agent-scopes.md) — Compiler/runtime mental model for worker scopes and tool resolution
- [Container Security Boundary](container-security-boundary.md) — Using Docker containers as security boundary for tool execution
- [Dynamic Workers Runtime Design](dynamic-agents-runtime-design.md) — Design for runtime creation and invocation of dynamic workers
- [Execution Mode Scripting Simplification](execution-mode-scripting-simplification.md) — Simplifying Python embedding with quick_run and Runner helpers
- [Execution Modes: User Stories](execution-modes-user-stories.md) — User stories for TUI, headless, and chat execution modes
- [Git Integration Research](git-integration-research.md) — Research on git integration patterns from Aider and golem-forge
- [Library System Specification](library-system-spec.md) — Specification for reusable worker and tool libraries
- [llm-do Project Mode, Worker Imports, and Tool Linking](llm-do-project-mode-and-imports.md) — Spec for project mode discovery, worker imports, and tool linking
- [llm-do vs vanilla PydanticAI: what the runtime adds](llm-do-vs-pydanticai-runtime.md) — What llm-do adds on top of vanilla PydanticAI agents
- [Preapproved Capability Scopes](preapproved-capability-scopes.md) — Path-scoped preapproval policies for reducing approval prompts
- [Pure Python vs MCP Code Mode](pure-python-vs-mcp-codemode.md) — Comparing MCP code mode with llm-do pure Python composite tools
- [Python Worker Annotation Brainstorm](python-agent-annotation-brainstorm.md) — Brainstorm for Python-only worker definitions via decorators
- [Recursive Worker Patterns (Summary)](recursive-patterns-summary.md) — Summary of recursive worker patterns for context-limited tasks
- [Recursive Problem Patterns for LLM Workers](recursive-problem-patterns.md) — Catalog of 15 problem types benefiting from recursive LLM workers
- [Stabilize Message Capture Without Private _agent_graph](stabilize-message-capture.md) — Removing private PydanticAI dependency for message capture
- [Tool Output Rendering Semantics](tool-output-rendering-semantics.md) — Semantic render hints for structured tool output display
- [Tool Result Truncation Metadata](tool-result-truncation.md) — Standardizing truncation metadata for tool results
- [Toolset Instantiation Questions](toolset-instantiation-questions.md) — Open questions on per-worker vs shared toolset instances
- [Event-Stream UI with Blocking Approvals](ui-event-stream-blocking-approvals.md) — Approval broker design for event-stream UI with blocking approvals
- [Unified Entry Function Design](unified-entry-function-design.md) — Design for unified tool plane across workers and entry functions

### Meta

- [Deferred Handler Minimal-Core Proposal Draft](meta/blocking_approvals.md) — Proposal for deferred_tool_handler enabling blocking approvals
- [LLM Day 2026 Warsaw - Presentation Proposal](meta/llm-day-2026-presentation.md) — LLM Day 2026 Warsaw conference presentation proposal
- [llm-do 5-Minute Meetup Demo Plan](meta/meetup-demo-plan.md) — 5-minute demo plan showing progressive stabilization workflow
- [PydanticAI Runtime Split and Trace Hooks](meta/pydanticai-runtime-trace.md) — Proposed PydanticAI changes for runtime/session split and tracing

### Research

- [Analysis: Adaptation of Agentic AI (arXiv:2512.16301)](research/adaptation-agentic-ai-analysis.md) — Analysis of agentic AI adaptation paper and llm-do implications
- [Experiment runtime without Worker class](research/experiment-runtime-without-worker.md) — Exploring runtime design without the Worker class
- [Manifest-Selected Entry Motivation](research/manifest-selected-entry-motivation.md) — Motivation for moving entry selection from worker to manifest
- [Type Catalog Review](research/type-catalog-review.md) — Review of type surface with simplification recommendations
