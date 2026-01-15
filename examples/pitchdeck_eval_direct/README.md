# Pitch Deck Evaluation (Direct Python)

This example demonstrates running llm-do workers **directly from Python** without using the `llm-do` CLI (step 3), plus a raw-Python refactor that bypasses the tool plane entirely (step 4). Python handles orchestration while the LLM handles analysis, and you can switch between TUI and headless output for step 3.

## The Pattern

```
run.py (step 3: tool plane)
    ├── list_pitchdecks() - discover PDFs
    ├── PITCH_EVALUATOR - create Worker
    ├── run_ui() - run entry with TUI or headless UI
    └── write results to disk

run_worker_entry.py (step 3: entry worker, tool plane)
    ├── build Worker objects directly
    ├── Runtime.run_entry() on the main worker
    └── main worker calls pitch_evaluator tool

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

# Step 3: worker entry (no @entry decorator)
uv run examples/pitchdeck_eval_direct/run_worker_entry.py
python examples/pitchdeck_eval_direct/run_worker_entry.py

# Step 4: raw Python (no approvals/events)
uv run examples/pitchdeck_eval_direct/run_raw.py
python examples/pitchdeck_eval_direct/run_raw.py
```

## Configuration

Edit constants at the top of `run.py` (step 3), `run_worker_entry.py` (step 3), or `run_raw.py` (step 4):

```python
# run.py
MODEL = "anthropic:claude-haiku-4-5"  # or "openai:gpt-4o-mini"
UI_MODE = "tui"  # or "headless"
APPROVAL_MODE = "prompt" if UI_MODE == "tui" else "approve_all"
VERBOSITY = 1  # 0=quiet, 1=tool calls, 2=stream
```

```python
# run_worker_entry.py
MODEL = "anthropic:claude-haiku-4-5"
APPROVAL_MODE = "approve_all"
VERBOSITY = 1  # 0=quiet, 1=normal, 2=stream
```

```python
# run_raw.py
MODEL = "anthropic:claude-haiku-4-5"
VERBOSITY = 3  # 0=quiet, 1=progress, 2=I/O details, 3=LLM messages
```

## Files

```
pitchdeck_eval_direct/
├── run.py                           # Main entry point
├── run_raw.py                       # Raw Python refactor (no tool plane)
├── run_worker_entry.py              # Worker entry (no @entry decorator)
├── instructions/
│   └── main.md                       # Main worker instructions
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

Entry workers can be invoked directly without a decorator (step 3):

```python
from llm_do.runtime import RunApprovalPolicy, Runtime, Worker, WorkerInput
from llm_do.toolsets.builtins import build_builtin_toolsets
from llm_do.toolsets.loader import ToolsetBuildContext, resolve_toolset_specs

pitch_evaluator = Worker(
    name="pitch_evaluator",
    model="anthropic:claude-haiku-4-5",
    instructions=Path("instructions/pitch_evaluator.md").read_text(),
)
builtin_toolsets = build_builtin_toolsets(Path.cwd(), Path("."))
available_toolsets = dict(
    builtin_toolsets,
    pitch_evaluator=pitch_evaluator.as_toolset_spec(),
)
toolset_context = ToolsetBuildContext(worker_name="main", available_toolsets=available_toolsets)
main_worker = Worker(
    name="main",
    model="anthropic:claude-haiku-4-5",
    instructions=Path("instructions/main.md").read_text(),
    toolset_specs=resolve_toolset_specs(["pitch_evaluator", "filesystem_project"], toolset_context),
    toolset_context=toolset_context,
)

policy = RunApprovalPolicy(mode="approve_all", return_permission_errors=True)
runtime = Runtime(
    project_root=Path("."),
    run_approval_policy=policy,
)
result, _ctx = await runtime.run_entry(main_worker, WorkerInput(input=""))
print(result)
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
