#!/usr/bin/env python
"""Pitch deck evaluation by calling an entry directly (no @entry).

Run with:
    uv run examples/pitchdeck_eval_direct/run_worker_entry.py
    python examples/pitchdeck_eval_direct/run_worker_entry.py
"""

import asyncio
from pathlib import Path

from llm_do.runtime import AgentEntry, RunApprovalPolicy, Runtime
from llm_do.runtime.events import RuntimeEvent
from llm_do.toolsets.builtins import build_builtin_toolsets
from llm_do.toolsets.loader import ToolsetBuildContext, resolve_toolset_specs
from llm_do.ui.adapter import adapt_event
from llm_do.ui.display import HeadlessDisplayBackend

# =============================================================================
# CONFIGURATION
# =============================================================================

MODEL = "anthropic:claude-haiku-4-5"
APPROVAL_MODE = "approve_all"  # "approve_all" or "reject_all"
VERBOSITY = 1  # 0=quiet, 1=normal, 2=stream

# =============================================================================
# Paths
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.resolve()
INSTRUCTIONS_DIR = PROJECT_ROOT / "instructions"
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "evaluations"

# =============================================================================
# Entries
# =============================================================================


def build_entry_worker() -> AgentEntry:
    """Build the entry and its evaluator tool entry."""
    pitch_evaluator = AgentEntry(
        name="pitch_evaluator",
        model=MODEL,
        instructions=(INSTRUCTIONS_DIR / "pitch_evaluator.md").read_text(),
    )

    builtin_toolsets = build_builtin_toolsets(Path.cwd(), PROJECT_ROOT)
    available_toolsets = dict(builtin_toolsets)
    available_toolsets["pitch_evaluator"] = pitch_evaluator.as_toolset_spec()

    toolset_context = ToolsetBuildContext(
        worker_name="main",
        available_toolsets=available_toolsets,
    )
    toolset_specs = resolve_toolset_specs(
        ["pitch_evaluator", "filesystem_project"],
        toolset_context,
    )

    main_worker = AgentEntry(
        name="main",
        model=MODEL,
        instructions=(INSTRUCTIONS_DIR / "main.md").read_text(),
        toolset_specs=toolset_specs,
        toolset_context=toolset_context,
    )
    return main_worker


# =============================================================================
# Runtime helpers
# =============================================================================


def build_runtime(verbosity: int) -> Runtime:
    """Construct a runtime with optional headless event logging."""
    policy = RunApprovalPolicy(mode=APPROVAL_MODE, return_permission_errors=True)
    if APPROVAL_MODE == "prompt":
        raise ValueError("Prompt approvals require run_ui(); use approve_all or reject_all.")

    on_event = None
    if verbosity > 0:
        backend = HeadlessDisplayBackend(verbosity=verbosity)

        def on_event_callback(event: RuntimeEvent) -> None:
            backend.display(adapt_event(event))

        on_event = on_event_callback

    return Runtime(
        project_root=PROJECT_ROOT,
        run_approval_policy=policy,
        on_event=on_event,
        verbosity=verbosity,
    )


async def run_entry_worker() -> str:
    """Run the entry worker, which calls the evaluator as a tool."""
    main_worker = build_entry_worker()
    runtime = build_runtime(VERBOSITY)
    result, _ctx = await runtime.run_entry(
        main_worker,
        "",  # Empty prompt - worker handles file discovery
    )
    return result


def cli_main() -> None:
    """Main entry point."""
    print(
        "Starting worker entry run with "
        f"MODEL={MODEL}, APPROVAL_MODE={APPROVAL_MODE}, VERBOSITY={VERBOSITY}"
    )
    print(f"Input directory: {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("-" * 60)

    outcome = asyncio.run(run_entry_worker())
    print(outcome)


if __name__ == "__main__":
    cli_main()
