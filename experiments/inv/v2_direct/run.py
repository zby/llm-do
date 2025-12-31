#!/usr/bin/env python
"""v2_direct: Run pitch deck evaluation directly with Python (no llm-do CLI).

Run with:
    cd experiments/inv/v2_direct
    python run.py

This script demonstrates running llm-do workers directly from Python,
with configuration constants for easy experimentation.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from llm_do.ctx_runtime import WorkerRuntime, WorkerInvocable
from llm_do.toolsets.filesystem import FileSystemToolset
from llm_do.ui.events import UIEvent
from llm_do.ui.display import HeadlessDisplayBackend
from pydantic_ai_blocking_approval import ApprovalToolset
from llm_do.ctx_runtime.approval_wrappers import make_headless_approval_callback

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

def wrap_with_approval(
    toolsets: list,
    approve_all: bool,
) -> list:
    """Wrap toolsets with ApprovalToolset for tool-level approval."""
    approval_callback = make_headless_approval_callback(
        approve_all=approve_all,
        reject_all=False,
        deny_note="Set APPROVE_ALL=True to auto-approve.",
    )

    wrapped = []
    for toolset in toolsets:
        # Recursively wrap nested toolsets in WorkerInvocable
        if isinstance(toolset, WorkerInvocable) and toolset.toolsets:
            toolset = WorkerInvocable(
                name=toolset.name,
                instructions=toolset.instructions,
                model=toolset.model,
                toolsets=wrap_with_approval(toolset.toolsets, approve_all),
                builtin_tools=toolset.builtin_tools,
                schema_in=toolset.schema_in,
                schema_out=toolset.schema_out,
            )
        wrapped.append(ApprovalToolset(
            inner=toolset,
            approval_callback=approval_callback,
        ))
    return wrapped


async def run_evaluation() -> str:
    """Run the pitch deck evaluation workflow."""
    main, _ = build_workers()

    # Set up display backend for progress output
    backend = HeadlessDisplayBackend(stream=sys.stderr, verbosity=VERBOSITY)

    def on_event(event: UIEvent) -> None:
        backend.display(event)

    # Wrap toolsets with approval
    wrapped_toolsets = wrap_with_approval(main.toolsets, APPROVE_ALL)

    # Create new main entry with wrapped toolsets
    main = WorkerInvocable(
        name=main.name,
        instructions=main.instructions,
        model=main.model,
        toolsets=wrapped_toolsets,
        builtin_tools=main.builtin_tools,
        schema_in=main.schema_in,
        schema_out=main.schema_out,
    )

    # Create runtime and run
    runtime = WorkerRuntime.from_entry(
        main,
        model=MODEL,
        on_event=on_event if VERBOSITY > 0 else None,
        verbosity=VERBOSITY,
    )

    result = await runtime.run(main, {"input": PROMPT})
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
