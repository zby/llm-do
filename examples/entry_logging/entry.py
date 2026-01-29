"""Entry function that logs user messages before calling the agent."""

from datetime import datetime
from pathlib import Path

from llm_do.runtime.args import get_display_text

# Log file in the same directory as this script
LOG_FILE = Path(__file__).parent / "messages.log"


async def main(input_data, runtime):
    """Log the user message and forward to the greeter agent."""
    # input_data is always a list of str | Attachment items
    text = get_display_text(input_data)

    # Log with timestamp
    timestamp = datetime.now().isoformat()
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {text}\n")

    # Forward to the greeter agent
    return await runtime.call_agent("main", input_data)
