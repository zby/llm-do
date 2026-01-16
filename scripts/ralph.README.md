# Ralph SLOC Reduction Loop

Reduce `llm_do` below TARGET_SLOC (see `ralph-config.sh`) while keeping all tests passing.

## Usage

```bash
# Check current state
./scripts/ralph-sloc-check.sh

# Run the loop (interactive, uses subscription)
./scripts/ralph-sloc-loop.sh
```

## Learning Log

The agent maintains `ralph-logs/attempts.md` to track:
- What was tried (successful and failed)
- Why failures occurred
- Lessons learned

This prevents repeating failed attempts across iterations.

## Exit Codes

- `0` - SUCCESS: SLOC < TARGET_SLOC with passing tests
- `2` - CONTINUE: keep looping
- `1` - ERROR: tests/lint/types failed

## Files

- `ralph-config.sh` - Configuration (TARGET_SLOC, LLM_DO_DIR)
- `ralph-sloc-check.sh` - Runs pytest, ruff, mypy, checks SLOC
- `ralph-sloc-prompt.md` - Instructions for the agent
- `ralph-sloc-loop.sh` - Main loop runner
- `ralph-logs/attempts.md` - Learning log (persists across runs)

## Reference

Based on the [Ralph Wiggum approach](https://www.aihero.dev/tips-for-ai-coding-with-ralph-wiggum).
