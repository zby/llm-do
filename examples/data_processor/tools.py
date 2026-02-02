"""Data processor tools using FunctionToolset.

These tools are wrapped by ApprovalToolset at runtime. The toolset definition
pre-approves the pure functions and leaves send_notification gated.
"""

from __future__ import annotations

from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import CallContext
from llm_do.toolsets.approval import set_toolset_approval_config


def build_data_tools(_ctx: RunContext[CallContext]) -> FunctionToolset:
    data_tools = FunctionToolset()

    @data_tools.tool
    def format_output(data: str, format: str = "csv") -> str:
        """Format data for output."""
        if format == "csv":
            return data.replace("\t", ",")
        if format == "json":
            import json

            lines = data.strip().split("\n")
            return json.dumps(lines, indent=2)
        return data

    @data_tools.tool
    def calculate_stats(numbers: str) -> str:
        """Calculate basic statistics on a comma-separated list of numbers."""
        nums = [float(x.strip()) for x in numbers.split(",") if x.strip()]
        if not nums:
            raise ValueError("No numbers provided")
        return f"count={len(nums)}, sum={sum(nums)}, avg={sum(nums)/len(nums):.2f}"

    @data_tools.tool
    def send_notification(message: str, channel: str = "default") -> str:
        """Send a notification message (stub)."""
        return f"Notification sent to {channel}: {message}"

    set_toolset_approval_config(
        data_tools,
        {
            "format_output": {"pre_approved": True},
            "calculate_stats": {"pre_approved": True},
        },
    )

    return data_tools


TOOLSETS = {"data_tools": build_data_tools}
