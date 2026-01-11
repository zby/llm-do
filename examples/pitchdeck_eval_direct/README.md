# Pitch Deck Evaluation (Direct Python)

This example demonstrates running llm-do workers **directly from Python** without using the `llm-do` CLI. Python handles all orchestration while the LLM handles analysis.

## The Pattern

```
run.py (Python script)
    ├── list_pitchdecks() - discover PDFs
    ├── build_pitch_evaluator() - create Worker
    ├── Runtime.run() - call LLM for each deck
    └── write results to disk
```

Compare to CLI-based versions:
- `pitchdeck_eval/` - LLM orchestrates via `.worker` files
- `pitchdeck_eval_code_entry/` - Python via `@entry` decorator, still uses CLI

## Why Direct Python?

- **No CLI dependency**: Run with standard `python` or `uv run`
- **Full control**: Customize Runtime, approval policies, verbosity
- **Easy integration**: Embed in larger Python applications
- **Debugging**: Standard Python debugging tools work normally

## Run

```bash
# From repo root
uv run examples/pitchdeck_eval_direct/run.py

# Or with python directly (requires dependencies)
python examples/pitchdeck_eval_direct/run.py
```

## Configuration

Edit constants at the top of `run.py`:

```python
MODEL = "anthropic:claude-haiku-4-5"  # or "openai:gpt-4o-mini"
APPROVAL_POLICY = RunApprovalPolicy(mode="approve_all")
VERBOSITY = 1  # 0=quiet, 1=tool calls, 2=stream
```

## Files

```
pitchdeck_eval_direct/
├── run.py                           # Main entry point
├── instructions/
│   └── pitch_evaluator.md           # LLM evaluator instructions
├── input/                           # Drop PDFs here
└── evaluations/                     # Reports written here
```

## Key Code

The core pattern for direct Python usage:

```python
from llm_do.runtime import RunApprovalPolicy, Runtime, Worker
from llm_do.ui.display import HeadlessDisplayBackend

# Build worker from instructions
evaluator = Worker(
    name="pitch_evaluator",
    model="anthropic:claude-haiku-4-5",
    instructions=Path("instructions/pitch_evaluator.md").read_text(),
    toolsets=[],
    base_path=Path(__file__).parent,  # For attachment resolution
)

# Create runtime
runtime = Runtime(
    cli_model="anthropic:claude-haiku-4-5",
    run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    on_event=HeadlessDisplayBackend(stream=sys.stderr, verbosity=1).display,
    verbosity=1,
)

# Run with input and attachments
result, _ctx = runtime.run(evaluator, {
    "input": "Evaluate this pitch deck.",
    "attachments": ["/path/to/deck.pdf"],
})
```
