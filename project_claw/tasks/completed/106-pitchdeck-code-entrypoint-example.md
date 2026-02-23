# Pitchdeck Evaluator: Code Entry Point Example

## Prerequisites

- [x] 105-custom-tool-context.md - Opt-in context injection for custom tools
- [x] tool-entry-point.md - Entry point is a tool, not a worker

## Goal

Demonstrate the tool-entry-point pattern by converting `pitchdeck_eval_stabilized` to use a Python `main()` function as entry point instead of an LLM orchestrator.

## Background

**Current state** (`examples/pitchdeck_eval_stabilized`):
```
main.worker (LLM orchestrator)
    ├── calls list_pitchdecks() tool
    ├── for each deck: calls pitch_evaluator worker
    └── writes results via filesystem tool
```

The orchestration logic is trivial - an LLM is overkill for:
1. List files
2. Loop over them
3. Call analyzer
4. Write results

**Target state**:
```
tools.py::main() (deterministic code)
    ├── calls list_pitchdecks() directly
    ├── for each deck: ctx.call_tool("pitch_evaluator", ...)
    └── writes results directly (Path.write_text)

pitch_evaluator.worker (unchanged - LLM analysis)
```

## Why This Example

1. **Real stabilizing benefit**: Removes token waste on trivial orchestration
2. **Demonstrates the pattern**: Deterministic entry → LLM workers for reasoning
3. **Incremental**: Already has `list_pitchdecks` stabilized, this completes it
4. **Testable**: Can verify same outputs with less LLM cost

## Tasks

- [x] Create new example directory `examples/pitchdeck_eval_code_entry/`
- [x] Copy `pitch_evaluator.worker` from stabilized example (unchanged)
- [x] Copy `PROCEDURE.md` (unchanged)
- [x] Create `tools.py` with:
  - [x] `list_pitchdecks()` (copy from stabilized)
  - [x] `main(ctx, input: str)` with `@tool_context` decorator
- [x] Implement `main()` function
- [x] Update example README explaining the pattern
- [x] Test: Run example and verify tool resolution works

## API Resolution

**call_tool signature for workers with attachments**: Option 2 was implemented.

```python
# Dict input with "input" and "attachments" keys
await ctx.call_tool("pitch_evaluator", {"input": "...", "attachments": ["path.pdf"]})
```

The `call_tool_async` function was updated to extract attachments from dict input:
- If `input_data` is a dict with "attachments" key, extract and pass to `call_worker_async`
- If dict has "input" key, use that as the worker input
- String input_data is passed through unchanged

## Implementation Notes

- Updated `llm_do/runtime.py::call_tool_async` to handle dict input with attachments
- Added test `test_call_tool_extracts_attachments_from_dict_input` in `tests/test_tool_entry_point.py`
- Example created at `examples/pitchdeck_eval_code_entry/`

## Success Criteria

1. [x] Example runs successfully with `llm-do` CLI (verified tool resolution)
2. [x] Clear README explaining the pattern and benefits
3. [x] Fewer LLM tokens used (no orchestration reasoning)

## Notes

- Keep `pitch_evaluator.worker` unchanged - LLM analysis is valuable there
- The pattern: code for mechanical ops, LLM for reasoning
- This is "full stabilizing" - only LLM calls are for actual analysis

## References

- Source example: `examples/pitchdeck_eval_stabilized/`
- New example: `examples/pitchdeck_eval_code_entry/`
- Design: `tasks/completed/tool-entry-point.md`
- Context injection: `tasks/completed/105-custom-tool-context.md`
