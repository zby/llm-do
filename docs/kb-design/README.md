# Meta

Observations and design work toward a knowledge base for llm-do's design history.

## Goal

Build a knowledge base that applies llm-do's own ideas — [crystallisation](../theory.md), stabilization, the generator/verifier pattern — to managing the project's design notes, decisions, and architecture. The knowledge base is both a practical tool and a showcase of the concepts from theory.md.

## Constraint: Claude Code as runtime

Opus is the best LLM for knowledge work, but the Anthropic API subscription can't be used with llm-do directly. So the knowledge base must be operational within Claude Code — using Claude Code's skills, hooks, and CLAUDE.md as the execution substrate.

This means we apply llm-do's *ideas* (stabilization, distribution boundaries, hybrid VM) but not its *code*. The implementation runs on Claude Code's machinery: markdown files, ripgrep queries, shell scripts, and skill definitions. Where llm-do would use Python orchestration, we use CLAUDE.md instructions and `.claude/skills/`.

## Approach

arscontexta is our first large experiment. These observations evaluate what works and inform what comes next:

- **What to keep** — machinery that earns its complexity (e.g., `/connect` for finding relationships)
- **What to simplify** — overhead that doesn't pay for itself (e.g., queue management, pipeline chaining)
- **What to build** — automated quality checks as they become justified by real failures, not taxonomy

The crystallisation gradient applies to the knowledge base itself:
1. Start soft — LLM writes and connects notes (stochastic)
2. Add filters — automated checks reject bad samples (deterministic code where possible, LLM rubrics where needed)
3. Stabilize search — recurring queries become indexes, tags, structured `rg` patterns
4. Stabilize the filters — LLM rubrics that prove reliable get replaced with deterministic checks

## Status

We're early. Record what you notice. Separate observations from prescriptions — note that something adds complexity before concluding what should replace it.
