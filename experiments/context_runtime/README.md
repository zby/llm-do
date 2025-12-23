# Context-Centric Runtime Experiment

This experiment prototypes a context-centric runtime where tools and workers
share a single callable protocol and all execution flows through `ctx.call()`.

## Goals
- Validate a unified registry for tools + workers
- Route all tool calls through `ctx` (approvals, depth limits, tracing)
- Build PydanticAI workers from lightweight configs

## Files
- `ctx.py` - Context + tools proxy + call dispatcher
- `registry.py` - Minimal registry for callable entries
- `entries.py` - ToolEntry + WorkerEntry implementations
- `tool_calling_model.py` - Mock model for deterministic tool call flows
- `demo.py` - Tiny demo using the ToolCallingModel
- `pitchdeck_demo.py` - Pitchdeck-style orchestration demo
- `pyproject.toml` - Standalone package configuration

## Installation (standalone)
```bash
cd experiments/context_runtime
uv venv
uv pip install -e .
```

## Run the demo
```bash
# From the experiment directory:
.venv/bin/python -m demo

# Or from the parent repo:
.venv/bin/python -m experiments.context_runtime.demo
```

## Run the pitch deck demo
```bash
# From the experiment directory:
.venv/bin/python -m pitchdeck_demo

# Or from the parent repo:
.venv/bin/python -m experiments.context_runtime.pitchdeck_demo
```

Notes:
- The demos use `tool_calling_model.py` to avoid real API calls.
- The pitch deck demo reads PDFs from `examples/pitchdeck_eval/input` and writes reports to `evaluations/`.
- This experiment is self-contained and does not require the parent `llm_do` package.
