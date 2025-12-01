# Example tools.py for data_processor worker
#
# Demonstrates custom tools with pydantic-ai-blocking-approval v0.4.0.
#
# IMPORTANT: All custom tools require approval by default (secure by default).
# The @requires_approval decorator has been REMOVED in v0.4.0.
# Approval is enforced at the wrapper level, not via decorator.


def format_output(data: str, format: str = "csv") -> str:
    """Format data for output.

    Will prompt for approval before execution (secure by default).
    """
    if format == "csv":
        return data.replace("\t", ",")
    elif format == "json":
        import json
        lines = data.strip().split("\n")
        return json.dumps(lines, indent=2)
    return data


def calculate_stats(numbers: str) -> str:
    """Calculate statistics on a list of numbers.

    Will prompt for approval before execution (secure by default).

    Args:
        numbers: Comma-separated list of numbers
    """
    nums = [float(x.strip()) for x in numbers.split(",")]
    return f"count={len(nums)}, sum={sum(nums)}, avg={sum(nums)/len(nums):.2f}"


def send_notification(message: str, channel: str = "default") -> str:
    """Send a notification message.

    Will prompt for approval before execution (secure by default).

    Args:
        message: The notification message
        channel: Target channel
    """
    # In real implementation, would send to notification service
    return f"Notification sent to {channel}: {message}"
