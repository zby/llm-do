# Data Processor Example

Demonstrates a Python `FunctionToolset` exposed to a worker, with per-tool approval configuration.

## What It Does

- Formats tab-separated data as CSV or JSON
- Calculates simple summary stats on a list of numbers
- Optionally “sends a notification” (stubbed)

## Usage

```bash
cd examples/data_processor
llm-do main.worker tools.py "Format this as CSV: a\tb\n1\t2\n\nAlso compute stats for: 1, 2, 3"
```

Try the gated tool (will require approval unless you pass `--approve-all`):

```bash
llm-do main.worker tools.py "Send a notification to ops: finished processing"
```

## Files

- `main.worker` — Worker prompt + tool approval config
- `tools.py` — `data_tools` (`FunctionToolset`) with `format_output`, `calculate_stats`, `send_notification`

