"""Stabilized data analysis tools.

Demonstrates progressive stabilization: the mechanical parts of
analyze_dataset (CSV parsing, statistics, trend detection) are now
deterministic Python code. The LLM is only called for narrative
interpretation — the part that actually requires reasoning.
"""

import csv
import json
from pathlib import Path
from statistics import mean, median

from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import CallContext
from llm_do.toolsets.approval import set_toolset_approval_config

PROJECT_ROOT = Path(__file__).parent.resolve()


def _compute_summary(rows: list[dict]) -> dict:
    """Compute summary statistics for numeric columns."""
    numeric_cols: dict[str, list[float]] = {}
    for row in rows:
        for key, value in row.items():
            try:
                numeric_cols.setdefault(key, []).append(float(value))
            except (ValueError, TypeError):
                pass

    stats = {}
    for col, values in numeric_cols.items():
        if not values:
            continue
        stats[col] = {
            "mean": round(mean(values), 2),
            "median": round(median(values), 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
        }
    return stats


def _detect_trends(rows: list[dict]) -> dict:
    """Detect simple trends by comparing first and second half."""
    numeric_cols: dict[str, list[float]] = {}
    for row in rows:
        for key, value in row.items():
            try:
                numeric_cols.setdefault(key, []).append(float(value))
            except (ValueError, TypeError):
                pass

    trends = {}
    for col, values in numeric_cols.items():
        if len(values) >= 2:
            mid = len(values) // 2
            first_half = mean(values[:mid])
            second_half = mean(values[mid:])
            change_pct = ((second_half - first_half) / first_half) * 100
            if change_pct > 5:
                direction = "increasing"
            elif change_pct < -5:
                direction = "decreasing"
            else:
                direction = "stable"
            trends[col] = {
                "direction": direction,
                "change_pct": round(change_pct, 1),
            }
    return trends


def _format_stats_table(stats: dict) -> str:
    """Format statistics as a markdown table."""
    lines = ["| Column | Mean | Median | Min | Max |",
             "|--------|------|--------|-----|-----|"]
    for col, s in stats.items():
        lines.append(f"| {col} | {s['mean']} | {s['median']} | {s['min']} | {s['max']} |")
    return "\n".join(lines)


def build_report_tools(_ctx: RunContext[CallContext]) -> FunctionToolset:
    """Build the report tools toolset."""
    tools = FunctionToolset()

    @tools.tool
    async def analyze_dataset(ctx: RunContext[CallContext], path: str) -> str:
        """Analyze a CSV dataset and produce a narrative report.

        Args:
            path: Path to the CSV file relative to the project root.
        """
        # Code: read and parse CSV (mechanical)
        full_path = PROJECT_ROOT / path
        with open(full_path) as f:
            rows = list(csv.DictReader(f))

        # Code: compute statistics (mechanical)
        stats = _compute_summary(rows)
        trends = _detect_trends(rows)

        # LLM: interpret findings and write narrative (reasoning)
        runtime = ctx.deps
        narrative = await runtime.call_agent(
            "write_narrative",
            {
                "input": (
                    f"Dataset: {path} ({len(rows)} rows)\n"
                    f"Columns: {', '.join(rows[0].keys())}\n\n"
                    f"Statistics:\n{json.dumps(stats, indent=2)}\n\n"
                    f"Trends:\n{json.dumps(trends, indent=2)}"
                ),
            },
        )

        # Code: assemble final report (mechanical)
        return (
            f"# Analysis: {Path(path).stem}\n\n"
            f"## Statistics\n\n{_format_stats_table(stats)}\n\n"
            f"## Trends\n\n{_format_trends_summary(trends)}\n\n"
            f"## Narrative\n\n{narrative}"
        )

    set_toolset_approval_config(
        tools,
        {"analyze_dataset": {"pre_approved": True}},
    )

    return tools


def _format_trends_summary(trends: dict) -> str:
    """Format trends as a bullet list."""
    lines = []
    for col, t in trends.items():
        lines.append(f"- **{col}**: {t['direction']} ({t['change_pct']:+.1f}%)")
    return "\n".join(lines)


TOOLSETS = {"report_tools": build_report_tools}
