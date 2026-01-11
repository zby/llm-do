# Resolve RunContext Model

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Ensure `RunContext.model` is always a concrete PydanticAI `Model` by resolving string models at the `RunContext` boundary.

## Context
- Relevant files/symbols: `llm_do/runtime/deps.py` (`WorkerRuntime._make_run_context`), `llm_do/runtime/contracts.py` (`ModelType`)
- Related tasks/notes/docs: `docs/notes/type-catalog-review.md`
- How to verify / reproduce: Add a direct tool call in a code entry path and confirm `ctx.model` is a `Model` instance (manual check or unit test).

## Decision Record
- Decision: Resolve string models before building `RunContext`.
- Inputs: PydanticAI expects `RunContext.model: Model`; llm-do currently casts `str | Model` to `Model`.
- Options: (1) resolve in `_make_run_context`, (2) split `ModelRef` vs `ResolvedModel` and refactor.
- Outcome: Choose option (1) for minimal change now.
- Follow-ups: Consider stronger type split if model resolution logic grows.

## Tasks
- [ ] Add model resolution in `WorkerRuntime._make_run_context` when `resolved_model` is a string
- [ ] Add a small test or minimal coverage (optional)
- [ ] Update `docs/notes/type-catalog-review.md` if behavior note changes

## Current State
Task created; no implementation yet.

## Notes
- Use `pydantic_ai.models.infer_model` for resolution.
- Beware of early env-var validation side effects; keep resolution narrowly scoped to `RunContext` creation.
