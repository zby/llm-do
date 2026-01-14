# Pitch Deck Evaluation (Direct Python)

This example demonstrates running llm-do workers **directly from Python** without using the `llm-do` CLI (step 3), plus a raw-Python refactor that bypasses the tool plane entirely (step 4). Python handles orchestration while the LLM handles analysis, and you can switch between TUI and headless output for step 3.

## The Pattern

```
run.py (step 3: tool plane)
    ├── list_pitchdecks() - discover PDFs
    ├── PITCH_EVALUATOR - create Worker
    ├── run_ui() - run entry with TUI or headless UI
    └── write results to disk

run_raw.py (step 4: raw Python)
    ├── list_pitchdecks() - discover PDFs
    ├── Agent() - call the model directly
    ├── build multimodal prompts manually
    └── write results to disk
```

Compare to CLI-based versions:
- `pitchdeck_eval/` - LLM orchestrates via `.worker` files
- `pitchdeck_eval_code_entry/` - Python via `@entry` decorator, still uses CLI

## Why Direct Python?

- **No CLI dependency**: Run with standard `python` or `uv run`
- **Full control**: Customize Runtime, approval policies, verbosity (step 3)
- **Easy integration**: Embed in larger Python applications
- **Debugging**: Standard Python debugging tools work normally
- **Raw escape hatch**: Step 4 bypasses approvals/events when you want a fully manual flow

## Run

```bash
# From repo root
uv run examples/pitchdeck_eval_direct/run.py

# Or with python directly (requires dependencies)
python examples/pitchdeck_eval_direct/run.py

# Step 4: raw Python (no approvals/events)
uv run examples/pitchdeck_eval_direct/run_raw.py
python examples/pitchdeck_eval_direct/run_raw.py
```

## Configuration

Edit constants at the top of `run.py`:

```python
MODEL = "anthropic:claude-haiku-4-5"  # or "openai:gpt-4o-mini"
UI_MODE = "tui"  # or "headless"
APPROVAL_MODE = "prompt" if UI_MODE == "tui" else "approve_all"
VERBOSITY = 1  # 0=quiet, 1=tool calls, 2=stream
```

## Files

```
pitchdeck_eval_direct/
├── run.py                           # Main entry point
├── run_raw.py                       # Raw Python refactor (no tool plane)
├── instructions/
│   └── pitch_evaluator.md           # LLM evaluator instructions
├── input/                           # Drop PDFs here
└── evaluations/                     # Reports written here
```

## Key Code

The core pattern for direct Python usage with switchable UI (step 3):

```python
from llm_do.runtime import Worker, entry
from llm_do.ui import run_ui

# Build worker from instructions
evaluator = Worker(
    name="pitch_evaluator",
    model="anthropic:claude-haiku-4-5",
    instructions=Path("instructions/pitch_evaluator.md").read_text(),
    toolsets=[],
)

# Run the entry with TUI or headless output
# project_root is used for resolving relative attachment paths
outcome = await run_ui(
    entry=main,
    input={"input": ""},
    model="anthropic:claude-haiku-4-5",
    project_root=Path(__file__).parent,
    approval_mode=APPROVAL_MODE,
    mode=UI_MODE,
    verbosity=1,
)
print(outcome.result)
```

Step 4 skips the tool plane (no approvals, no events, no tool wrappers):

```python
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent

agent = Agent(model="anthropic:claude-haiku-4-5", instructions="...")
attachment = BinaryContent(data=Path("deck.pdf").read_bytes(), media_type="application/pdf")
result = await agent.run(["Evaluate this pitch deck.", attachment])
print(result.output)
```
