# Pitch Deck Evaluation (Direct Python)

This example demonstrates running llm-do **directly from Python** without the CLI. Three scripts show different levels of abstraction, helping you choose the right approach for your use case.

## The Scripts

| Script | Orchestration | Uses llm-do | Tool Plane |
|--------|---------------|-------------|------------|
| `run.py` | Python code | Yes | Yes (approvals, events) |
| `run_agent_entry.py` | LLM agent | Yes | Yes (approvals, events) |
| `run_raw.py` | Python code | No | No (raw PydanticAI) |

### run.py - Code Entry with UI

Python handles the orchestration loop. The LLM only evaluates decks.

```
Python main() → runtime.call_agent("pitch_evaluator") → write results
```

This is the recommended approach when orchestration is mechanical (list files, loop, write results). Python code is deterministic, testable, and doesn't waste tokens on trivial decisions.

```python
from llm_do.runtime import AgentSpec, FunctionEntry, CallContext
from llm_do.ui import run_ui

EVALUATOR = AgentSpec(
    name="pitch_evaluator",
    model="anthropic:claude-haiku-4-5",
    instructions=Path("instructions/pitch_evaluator.md").read_text(),
)

async def main(_input_data, runtime: CallContext) -> str:
    for deck in list_pitchdecks():
        report = await runtime.call_agent(EVALUATOR, {
            "input": "Evaluate this pitch deck.",
            "attachments": [deck["file"]],
        })
        Path(deck["output_path"]).write_text(report)
    return "Done"

ENTRY = FunctionEntry(name="main", main=main)

# Run with TUI or headless output
outcome = await run_ui(
    entry=ENTRY,
    input={"input": ""},
    project_root=Path(__file__).parent,
    approval_mode="approve_all",  # or "prompt" for interactive
    mode="headless",  # or "tui"
)
```

### run_agent_entry.py - Agent Entry

An LLM main agent orchestrates, calling pitch_evaluator as a tool. The LLM decides what to do based on its instructions.

```
Python → Runtime.run_entry() → LLM main agent → pitch_evaluator tool
```

Use this when orchestration requires judgment or flexibility that benefits from LLM reasoning. The main agent can adapt to unexpected situations, handle errors creatively, or make decisions about which files to process.

```python
from llm_do.runtime import AgentSpec, FunctionEntry, RunApprovalPolicy, Runtime
from llm_do.toolsets.agent import agent_as_toolset
from llm_do.toolsets.builtins import build_builtin_toolsets

# Build agents and wire toolsets
pitch_evaluator = AgentSpec(name="pitch_evaluator", model=MODEL, instructions=...)
main_agent = AgentSpec(
    name="main",
    model=MODEL,
    instructions=Path("instructions/main.md").read_text(),
    toolset_specs=[
        builtin_toolsets["filesystem_project"],
        agent_as_toolset(pitch_evaluator, tool_name="pitch_evaluator"),
    ],
)

async def main(input_data, runtime):
    return await runtime.call_agent(main_agent, input_data)

entry = FunctionEntry(name="main", main=main)
runtime = Runtime(project_root=Path("."), run_approval_policy=policy)
result, _ctx = await runtime.run_entry(entry, "")
```

### run_raw.py - Raw PydanticAI

Bypasses llm-do entirely. Uses PydanticAI's `Agent` directly with `BinaryContent` for PDFs.

```
Python → Agent.run() with PDF attachment → write results
```

No approvals, no events, no tool wrappers. Use this when:
- You don't need approval workflows
- You don't need event logging/observability
- You want minimal dependencies
- You're prototyping or debugging

```python
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent

agent = Agent(model="anthropic:claude-haiku-4-5", instructions="...")
attachment = BinaryContent(
    data=Path("deck.pdf").read_bytes(),
    media_type="application/pdf",
)
result = await agent.run(["Evaluate this pitch deck.", attachment])
print(result.output)
```

## What the Tool Plane Provides

When you use llm-do (run.py or run_agent_entry.py), you get:

- **Approvals**: Interactive or policy-based approval of tool calls
- **Events**: Structured logging of all agent activity
- **Attachments**: Automatic handling of file attachments with path resolution
- **Depth limits**: Protection against runaway agent recursion
- **UI options**: TUI for interactive use, headless for automation

When you use raw PydanticAI (run_raw.py), you bypass all of this. You're responsible for building prompts, handling attachments, and logging.

## Why Direct Python?

- **No CLI dependency**: Run with `python` or `uv run`
- **Full control**: Customize Runtime, approval policies, verbosity
- **Easy integration**: Embed in larger Python applications
- **Debugging**: Standard Python debugging tools work normally

## Run

```bash
# Code entry with TUI/headless UI
uv run examples/pitchdeck_eval_direct/run.py

# Agent entry (LLM orchestrates)
uv run examples/pitchdeck_eval_direct/run_agent_entry.py

# Raw PydanticAI (no llm-do)
uv run examples/pitchdeck_eval_direct/run_raw.py
```

## Configuration

Edit constants at the top of each script:

```python
MODEL = "anthropic:claude-haiku-4-5"  # must support PDF/vision
UI_MODE = "tui"  # or "headless" (run.py only)
APPROVAL_MODE = "approve_all"  # or "prompt" for interactive
VERBOSITY = 1  # 0=quiet, 1=normal, 2=verbose
```

## Files

```
pitchdeck_eval_direct/
├── run.py                  # Code entry with run_ui()
├── run_agent_entry.py     # Agent entry with Runtime.run_entry()
├── run_raw.py              # Raw PydanticAI
├── instructions/
│   ├── main.md             # Main agent instructions (for run_agent_entry.py)
│   └── pitch_evaluator.md  # Evaluator instructions
├── input/                  # Drop PDFs here
└── evaluations/            # Reports written here
```

## Compare to CLI-based versions

- `pitchdeck_eval/` - LLM orchestrates via `.agent` files, uses CLI
- `pitchdeck_eval_code_entry/` - Python entry via `FunctionEntry`, uses CLI
