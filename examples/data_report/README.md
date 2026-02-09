# Data Report — All LLM (Prototype)

Analyzes CSV datasets and produces narrative reports. The LLM does
everything: reads the CSV, computes statistics, identifies trends,
and writes the narrative.

This is the "Version 1" prototype. Compare with
[data_report_stabilized](../data_report_stabilized/) to see the same
task after progressive stabilization — mechanical work moved to Python
code, LLM focused on interpretation.

## Running

```bash
LLM_DO_MODEL=anthropic:claude-haiku-4-5 llm-do examples/data_report/
```

## Structure

- `main.agent` — orchestrator: lists CSV files, calls `analyze_dataset`, writes reports
- `analyze_dataset.agent` — LLM reads CSV and produces the full analysis
- `schemas.py` — custom input model (`DatasetInput`) so the agent accepts a `path` parameter
- `input/` — sample CSV data
- `reports/` — generated reports (gitignored contents)

## What to notice

The LLM is computing averages and medians — purely mechanical work that
wastes tokens and sometimes produces wrong results. The narrative
interpretation is the only part that actually needs reasoning.
