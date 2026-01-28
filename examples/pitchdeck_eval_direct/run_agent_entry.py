#!/usr/bin/env python
"""Pitch deck evaluation by calling an agent entry directly (no code entry toolset).

Run with:
    uv run examples/pitchdeck_eval_direct/run_agent_entry.py
    python examples/pitchdeck_eval_direct/run_agent_entry.py
"""

import asyncio
from pathlib import Path

from llm_do.runtime import AgentSpec, FunctionEntry, RunApprovalPolicy, Runtime
from llm_do.runtime.events import RuntimeEvent
from llm_do.toolsets.agent import agent_as_toolset
from llm_do.toolsets.builtins import build_builtin_toolsets
from llm_do.ui.adapter import adapt_event
from llm_do.ui.display import HeadlessDisplayBackend

# =============================================================================
# CONFIGURATION
# =============================================================================

import os

MODEL = os.environ.get("LLM_DO_MODEL")
if not MODEL:
    raise RuntimeError("LLM_DO_MODEL environment variable is required")
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
# Agents
# =============================================================================


def build_entry() -> FunctionEntry:
    """Build the entry and its evaluator agent."""
    pitch_evaluator = AgentSpec(
        name="pitch_evaluator",
        model=MODEL,
        instructions=(INSTRUCTIONS_DIR / "pitch_evaluator.md").read_text(),
    )

    builtin_toolsets = build_builtin_toolsets(Path.cwd(), PROJECT_ROOT)
    toolset_specs = [
        builtin_toolsets["filesystem_project"],
        agent_as_toolset(pitch_evaluator, tool_name="pitch_evaluator"),
    ]

    main_agent = AgentSpec(
        name="main",
        model=MODEL,
        instructions=(INSTRUCTIONS_DIR / "main.md").read_text(),
        toolset_specs=toolset_specs,
    )

    async def main(input_data, runtime) -> str:
        return await runtime.call_agent(main_agent, input_data)

    return FunctionEntry(
        name=main_agent.name,
        fn=main,
        schema_in=main_agent.schema_in,
    )


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
            ui_event = adapt_event(event)
            if ui_event is not None:
                backend.display(ui_event)

        on_event = on_event_callback

    return Runtime(
        project_root=PROJECT_ROOT,
        run_approval_policy=policy,
        on_event=on_event,
        verbosity=verbosity,
    )


async def run_entry_agent() -> str:
    """Run the entry agent, which calls the evaluator as a tool."""
    entry = build_entry()
    runtime = build_runtime(VERBOSITY)
    result, _ctx = await runtime.run_entry(
        entry,
        "",  # Empty prompt - agent handles file discovery
    )
    return result


def cli_main() -> None:
    """Main entry point."""
    print(
        "Starting agent entry run with "
        f"MODEL={MODEL}, APPROVAL_MODE={APPROVAL_MODE}, VERBOSITY={VERBOSITY}"
    )
    print(f"Input directory: {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("-" * 60)

    outcome = asyncio.run(run_entry_agent())
    print(outcome)


if __name__ == "__main__":
    cli_main()
