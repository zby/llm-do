# Data Processor Example

Demonstrates a Python `FunctionToolset` exposed to a agent, with per-tool approval configuration.

## What It Does

- Formats tab-separated data as CSV or JSON
- Calculates simple summary stats on a list of numbers
- Optionally “sends a notification” (stubbed)

## Usage

```bash
llm-do examples/data_processor/project.json "Format this as CSV: a\tb\n1\t2\n\nAlso compute stats for: 1, 2, 3"
```

Try the gated tool (change `approval_mode` in project.json to `"prompt"` first):

```bash
llm-do examples/data_processor/project.json "Send a notification to ops: finished processing"
```

## Files

- `project.json` — Manifest defining entry point and files
- `main.agent` — Worker prompt + tool approval config
- `tools.py` — `data_tools` (`FunctionToolset`) with `format_output`, `calculate_stats`, `send_notification`

