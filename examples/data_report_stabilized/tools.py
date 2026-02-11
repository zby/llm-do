"""Stabilized data analysis tools.

Demonstrates progressive stabilization: the mechanical parts of
analyze_dataset (CSV parsing, statistics, trend detection) are now
deterministic Python code. The LLM is only called for narrative
interpretation — the part that actually requires reasoning.
"""

import csv
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


def build_report_tools(_ctx: RunContext[CallContext]) -> FunctionToolset:
    """Build the report tools toolset."""
    tools = FunctionToolset()

    @tools.tool
    async def analyze_dataset(ctx: RunContext[CallContext], path: str) -> str:
        """Analyze a CSV dataset and produce a narrative report.

        Args:
            path: Path to the CSV file relative to the project root.
        """
        full_path = PROJECT_ROOT / path
        rows = list(csv.DictReader(open(full_path)))  # Code (mechanical)
        stats = _compute_summary(rows)                 # Code (mechanical)
        trends = _detect_trends(rows)                  # Code (mechanical)

        runtime = ctx.deps                             # LLM (reasoning)
        narrative = await runtime.call_agent(
            "write_narrative",
            {"input": f"Stats: {stats}\nTrends: {trends}"},
        )
        return narrative

    set_toolset_approval_config(
        tools,
        {"analyze_dataset": {"pre_approved": True}},
    )

    return tools


TOOLSETS = {"report_tools": build_report_tools}
