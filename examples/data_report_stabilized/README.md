# Data Report — Stabilized (Hybrid)

Analyzes CSV datasets and produces narrative reports. Mechanical work
(CSV parsing, statistics, trend detection) is now deterministic Python
code. The LLM is only called for narrative interpretation — the part
that actually requires reasoning.

This is the stabilized version of [data_report](../data_report/).
The calling prompt in `main.agent` is identical — only the implementation
of `analyze_dataset` changed from an LLM agent to a Python function.

## Running

```bash
LLM_DO_MODEL=anthropic:claude-haiku-4-5 llm-do examples/data_report_stabilized/
```

## Structure

- `main.agent` — orchestrator (same calling instruction as V1)
- `tools.py` — `analyze_dataset` as a Python function: reads CSV, computes
  stats, detects trends, then calls `write_narrative` agent for interpretation
- `write_narrative.agent` — LLM writes the narrative from pre-computed data
- `input/` — same sample CSV data
- `reports/` — generated reports (gitignored contents)

## What changed

| Responsibility       | V1 (data_report)  | V2 (this)          |
|----------------------|-------------------|--------------------|
| Parse CSV            | LLM               | Python (csv module) |
| Compute statistics   | LLM               | Python (statistics) |
| Detect trends        | LLM               | Python             |
| Write narrative      | LLM               | LLM (write_narrative agent) |
| Format final report  | LLM               | Python             |

## What stayed the same

The call site in `main.agent`: `analyze_dataset(path=<csv_path>)`.
Same name, same arguments. The caller never knew the implementation changed.
