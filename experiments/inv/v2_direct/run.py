#!/usr/bin/env python
"""v2_direct: Run pitch deck evaluation directly with Python (no llm-do CLI).

Run with:
    uv run experiments/inv/v2_direct/run.py
    uv run -m experiments.inv.v2_direct.run

This script demonstrates running llm-do workers directly from Python,
with configuration constants for easy experimentation.
"""

import sys
from pathlib import Path

from llm_do.runtime import RunApprovalPolicy, Runtime, Worker
from llm_do.toolsets.filesystem import FileSystemToolset
from llm_do.ui.display import HeadlessDisplayBackend

# =============================================================================
# CONFIGURATION - Edit these constants to experiment
# =============================================================================

# Model selection
MODEL = "anthropic:claude-haiku-4-5"
# MODEL = "openai:gpt-4o-mini"
# MODEL = "anthropic:claude-sonnet-4-20250514"

# Approval settings
APPROVAL_POLICY = RunApprovalPolicy(
    mode="approve_all",  # For headless safety, use "reject_all" to deny tool approvals.
)

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


def build_workers() -> tuple[Worker, Worker]:
    """Build and return the worker entries."""
    # NOTE: base_path must be configured separately on FileSystemToolset and on
    # workers that receive attachments. This duplication is not ideal - a cleaner
    # solution would unify path resolution at the runtime level.
    filesystem = FileSystemToolset(config={"base_path": str(HERE)})

    pitch_evaluator = Worker(
        name="pitch_evaluator",
        model=MODEL,
        instructions=load_instructions("pitch_evaluator"),
        toolsets=[],
        base_path=HERE,  # For resolving attachment paths
    )

    main = Worker(
        name="main",
        model=MODEL,
        instructions=load_instructions("main"),
        toolsets=[filesystem, pitch_evaluator.as_toolset()],
    )

    return main, pitch_evaluator


# =============================================================================
# Runtime
# =============================================================================

def run_evaluation() -> str:
    """Run the pitch deck evaluation workflow."""
    main, _pitch_evaluator = build_workers()

    # Set up display backend for progress output
    backend = HeadlessDisplayBackend(stream=sys.stderr, verbosity=VERBOSITY)

    runtime = Runtime(
        cli_model=MODEL,
        run_approval_policy=APPROVAL_POLICY,
        on_event=backend.display if VERBOSITY > 0 else None,
        verbosity=VERBOSITY,
    )
    result, _ctx = runtime.run(main, {"input": PROMPT})
    return result


def main():
    """Main entry point."""
    print(f"Running with MODEL={MODEL}, APPROVAL_MODE={APPROVAL_POLICY.mode}, VERBOSITY={VERBOSITY}")
    print("-" * 60)

    result = run_evaluation()

    print("-" * 60)
    print("RESULT:")
    print(result)


if __name__ == "__main__":
    main()
