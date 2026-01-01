#!/usr/bin/env python
"""v2_direct: Run pitch deck evaluation directly with Python (no llm-do CLI).

Run with:
    uv run experiments/inv/v2_direct/run.py
    uv run -m experiments.inv.v2_direct.run

This script demonstrates running llm-do workers directly from Python,
with configuration constants for easy experimentation.
"""

import asyncio
import sys
from pathlib import Path

from llm_do.ctx_runtime import ApprovalPolicy, WorkerInvocable, run_entry
from llm_do.toolsets.filesystem import FileSystemToolset
from llm_do.ui.display import HeadlessDisplayBackend
from llm_do.ui.events import UIEvent

# =============================================================================
# CONFIGURATION - Edit these constants to experiment
# =============================================================================

# Model selection
MODEL = "anthropic:claude-haiku-4-5"
# MODEL = "openai:gpt-4o-mini"
# MODEL = "anthropic:claude-sonnet-4-20250514"

# Approval settings
APPROVE_ALL = True  # Set to False to require manual approval for tools

# Verbosity: 0=quiet, 1=show tool calls, 2=stream responses
VERBOSITY = 1

# Prompt to send
PROMPT = "Go"

# =============================================================================
# Worker definitions
# =============================================================================

HERE = Path(__file__).parent


def load_instructions(name: str) -> str:
    """Load instructions from the instructions/ directory."""
    return (HERE / "instructions" / f"{name}.md").read_text()


def build_workers() -> tuple[WorkerInvocable, WorkerInvocable]:
    """Build and return the worker entries."""
    filesystem = FileSystemToolset(config={})

    pitch_evaluator = WorkerInvocable(
        name="pitch_evaluator",
        model=MODEL,
        instructions=load_instructions("pitch_evaluator"),
        toolsets=[],
    )

    main = WorkerInvocable(
        name="main",
        model=MODEL,
        instructions=load_instructions("main"),
        toolsets=[filesystem, pitch_evaluator],
    )

    return main, pitch_evaluator


# =============================================================================
# Runtime
# =============================================================================

async def run_evaluation() -> str:
    """Run the pitch deck evaluation workflow."""
    main, _ = build_workers()

    # Set up display backend for progress output
    backend = HeadlessDisplayBackend(stream=sys.stderr, verbosity=VERBOSITY)

    def on_event(event: UIEvent) -> None:
        backend.display(event)

    approval_policy = ApprovalPolicy(
        mode="approve_all" if APPROVE_ALL else "prompt",
    )
    result, _ctx = await run_entry(
        entry=main,
        prompt=PROMPT,
        model=MODEL,
        approval_policy=approval_policy,
        on_event=on_event if VERBOSITY > 0 else None,
        verbosity=VERBOSITY,
    )
    return result


def main():
    """Main entry point."""
    print(f"Running with MODEL={MODEL}, APPROVE_ALL={APPROVE_ALL}, VERBOSITY={VERBOSITY}")
    print("-" * 60)

    result = asyncio.run(run_evaluation())

    print("-" * 60)
    print("RESULT:")
    print(result)


if __name__ == "__main__":
    main()
