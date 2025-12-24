"""Example tools.py for a data_processor worker.

Demonstrates FunctionToolset tools under ctx_runtime. These tools are wrapped by
ApprovalToolset at runtime; without --approve-all, each tool call requires user
approval unless a toolset defines its own needs_approval rules.
"""
from pydantic_ai.toolsets import FunctionToolset

tools = FunctionToolset()


@tools.tool
def format_output(data: str, format: str = "csv") -> str:
    """Format data for output."""
    if format == "csv":
        return data.replace("\t", ",")
    if format == "json":
        import json
        lines = data.strip().split("\n")
        return json.dumps(lines, indent=2)
    return data


@tools.tool
def calculate_stats(numbers: str) -> str:
    """Calculate statistics on a list of numbers.

    Args:
        numbers: Comma-separated list of numbers
    """
    nums = [float(x.strip()) for x in numbers.split(",")]
    return f"count={len(nums)}, sum={sum(nums)}, avg={sum(nums)/len(nums):.2f}"


@tools.tool
def send_notification(message: str, channel: str = "default") -> str:
    """Send a notification message.

    Args:
        message: The notification message
        channel: Target channel
    """
    return f"Notification sent to {channel}: {message}"
