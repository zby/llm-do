# Schema Composition as Function Types

## Status
exploring design

## Goal
Add examples demonstrating how input/output schemas enable composition, treating agents as typed functions: `Agent : schema_in → schema_out`.

## Context
- Relevant files: `llm_do/runtime/args.py`, `llm_do/runtime/contracts.py`, `llm_do/runtime/schema_refs.py`
- Existing example: `examples/recursive_task_decomposer/schemas.py`
- Current state: `schema_in` (WorkerArgs) and `schema_out` (BaseModel) exist but composition is implicit

## Design Questions
1. **Strict vs structural typing** - Should `Agent1.schema_out` exactly equal `Agent2.schema_in`, or allow structural compatibility (output has fields that input needs)?
2. **Transformation location** - When schemas don't match exactly, should there be explicit adapters, or should composition automatically map compatible fields?
3. **Declaration style** - Should composition be expressible in worker files (YAML), or only in Python?

## Current Architecture
- Input schemas extend `WorkerArgs`, define structure + `prompt_messages()` conversion
- Output schemas are plain `BaseModel`, validated by PydanticAI
- Schemas exposed as JSON schemas for tool definitions
- No verification that one agent's output matches another's input

## Tasks
- [ ] Resolve design questions above
- [ ] Create example showing basic composition: Agent1.schema_out → Agent2.schema_in
- [ ] Create example showing pipeline of 2-3 agents with typed flow
- [ ] Document the function-type mental model
- [ ] Consider: static verification tooling for schema compatibility

## Example Problem
```python
# Current: manual, unverified composition
result = await call_agent("planner", PlannerInput(task="..."))  # → Plan
await call_agent("executor", ExecutorInput(plan=result))  # type mismatch risk

# Desired: verified composition
pipeline = compose(planner, executor)  # Pipeline: PlannerInput → ExecutionResult
```

## Verification
- Examples should run end-to-end with real LLM calls
- Type mismatches should be caught at composition time, not runtime
