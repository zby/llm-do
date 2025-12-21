# Pitchdeck Evaluator: Code Entry Point Example

## Prerequisites

- [ ] 105-custom-tool-context.md - Opt-in context injection for custom tools
- [ ] tool-entry-point.md - Entry point is a tool, not a worker

## Goal

Demonstrate the tool-entry-point pattern by converting `pitchdeck_eval_hardened` to use a Python `main()` function as entry point instead of an LLM orchestrator.

## Background

**Current state** (`examples/pitchdeck_eval_hardened`):
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

1. **Real hardening benefit**: Removes token waste on trivial orchestration
2. **Demonstrates the pattern**: Deterministic entry → LLM workers for reasoning
3. **Incremental**: Already has `list_pitchdecks` hardened, this completes it
4. **Testable**: Can verify same outputs with less LLM cost

## Tasks

- [ ] Create new example directory `examples/pitchdeck_eval_code_entry/`
- [ ] Copy `pitch_evaluator.worker` from hardened example (unchanged)
- [ ] Copy `PROCEDURE.md` (unchanged)
- [ ] Create `tools.py` with:
  - [ ] `list_pitchdecks()` (copy from hardened)
  - [ ] `main(ctx, input: str)` with `@with_context` decorator
- [ ] Implement `main()` function:
  ```python
  @with_context
  async def main(ctx: ToolContext, input: str) -> str:
      """Evaluate all pitch decks in input directory."""
      decks = list_pitchdecks()
      results = []

      for deck in decks:
          # Call LLM worker for analysis
          report = await ctx.call_tool(
              "pitch_evaluator",
              f"Evaluate this pitch deck.",
              attachments=[deck["file"]]
          )

          # Write result (deterministic)
          Path(deck["output_path"]).parent.mkdir(exist_ok=True)
          Path(deck["output_path"]).write_text(report)
          results.append(deck["slug"])

      return f"Evaluated {len(results)} pitch decks: {', '.join(results)}"
  ```
- [ ] Update example README explaining the pattern
- [ ] Test: Run example and verify same output quality as LLM-orchestrated version

## API Considerations

The `main()` signature needs to handle attachments. Options:

**Option A**: Attachments passed separately
```python
async def main(ctx: ToolContext, input: str) -> str:
    # ctx has attachments available
```

**Option B**: Attachments as parameter
```python
async def main(ctx: ToolContext, input: str, attachments: list[str] = None) -> str:
```

For this example, attachments come from `list_pitchdecks()` output, not CLI input, so Option A is fine.

## call_tool Signature

Need to clarify how `call_tool` handles attachments for workers:

```python
# Option 1: Separate parameter
await ctx.call_tool("pitch_evaluator", input="...", attachments=["path.pdf"])

# Option 2: Dict input (matches current worker_call)
await ctx.call_tool("pitch_evaluator", {"input": "...", "attachments": ["path.pdf"]})
```

Resolve during tool-entry-point.md implementation.

## Success Criteria

1. Example runs successfully with `llm-do` CLI
2. Output quality matches LLM-orchestrated version
3. Fewer LLM tokens used (no orchestration reasoning)
4. Clear README explaining the pattern and benefits

## Notes

- Keep `pitch_evaluator.worker` unchanged - LLM analysis is valuable there
- The pattern: code for mechanical ops, LLM for reasoning
- This is "full hardening" - only LLM calls are for actual analysis

## References

- Source example: `examples/pitchdeck_eval_hardened/`
- Design: `docs/tasks/active/tool-entry-point.md`
- Context injection: `docs/tasks/active/105-custom-tool-context.md`
