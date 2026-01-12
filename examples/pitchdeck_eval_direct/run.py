#!/usr/bin/env python
"""Pitch deck evaluation with TUI and interactive approvals.

Run with:
    uv run examples/pitchdeck_eval_direct/run.py
    python examples/pitchdeck_eval_direct/run.py

This script demonstrates running llm-do workers with a Textual TUI,
including interactive approval prompts for tool calls.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

try:
    from slugify import slugify
except ImportError:
    raise ImportError(
        "python-slugify required. Install with: pip install python-slugify"
    )

from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalRequest

from llm_do.runtime import (
    RunApprovalPolicy,
    Runtime,
    Worker,
    WorkerArgs,
    WorkerInput,
    WorkerRuntime,
    build_entry,
    entry,
)
from llm_do.ui import UIEvent, parse_approval_request
from llm_do.ui.display import TextualDisplayBackend

# =============================================================================
# CONFIGURATION - Edit these constants to experiment
# =============================================================================

# Model selection
MODEL = "anthropic:claude-haiku-4-5"
# MODEL = "openai:gpt-4o-mini"
# MODEL = "anthropic:claude-sonnet-4-20250514"

# Approval mode: "prompt" for interactive, "approve_all" to skip prompts
APPROVAL_MODE = "prompt"

# Verbosity: 1=show tool calls, 2=stream responses
VERBOSITY = 1

# =============================================================================
# Paths
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.resolve()
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "evaluations"

# =============================================================================
# Worker (global - Workers are reusable across runs)
# =============================================================================

PITCH_EVALUATOR = Worker(
    name="pitch_evaluator",
    model=MODEL,
    instructions=(PROJECT_ROOT / "instructions" / "pitch_evaluator.md").read_text(),
    toolsets=[],
    base_path=PROJECT_ROOT,  # For resolving attachment paths
)

# =============================================================================
# File discovery
# =============================================================================


def list_pitchdecks(input_dir: str = "input") -> list[dict]:
    """List pitch deck PDFs with pre-computed slugs and output paths.

    Args:
        input_dir: Directory to scan for PDF files, relative to project root.

    Returns:
        List of dicts with keys:
        - file: Absolute path to the PDF file
        - slug: URL-safe slug derived from filename
        - output_path: Absolute path for the evaluation report
    """
    input_path = PROJECT_ROOT / input_dir
    result = []
    if input_path.exists():
        for pdf in sorted(input_path.glob("*.pdf")):
            slug = slugify(pdf.stem)
            result.append({
                "file": str(pdf.resolve()),
                "slug": slug,
                "output_path": str((OUTPUT_DIR / f"{slug}.md").resolve()),
            })
    return result


# =============================================================================
# Entry point
# =============================================================================


@entry(toolsets=[PITCH_EVALUATOR.as_toolset()])
async def main(args: WorkerArgs, runtime: WorkerRuntime) -> str:
    """Evaluate all pitch decks in input directory.

    This is a code entry point that orchestrates the evaluation workflow:
    1. List all pitch deck PDFs (deterministic)
    2. Call LLM worker for each deck (LLM reasoning)
    3. Write results to files (deterministic)

    File paths are relative to the project root (this file's directory).

    Args:
        args: WorkerArgs input (ignored - workflow is deterministic)
        runtime: WorkerRuntime for calling workers
    """
    decks = list_pitchdecks()

    if not decks:
        return "No pitch decks found in input directory."

    results = []

    for deck in decks:
        report = await runtime.call(
            "pitch_evaluator",
            WorkerInput(
                input="Evaluate this pitch deck.",
                attachments=[deck["file"]],
            ),
        )

        # Write result (deterministic)
        output_path = Path(deck["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        results.append(deck["slug"])

    return f"Evaluated {len(results)} pitch deck(s): {', '.join(results)}"


# =============================================================================
# TUI Runtime
# =============================================================================


def _ensure_stdout_textual_driver() -> None:
    """Configure Textual to write TUI output to stdout on Linux."""
    if sys.platform.startswith("win"):
        return
    if os.environ.get("TEXTUAL_DRIVER"):
        return

    os.environ["TEXTUAL_DRIVER"] = f"{__name__}:StdoutLinuxDriver"

    from textual.drivers.linux_driver import LinuxDriver

    class StdoutLinuxDriver(LinuxDriver):
        def __init__(
            self,
            app: Any,
            *,
            debug: bool = False,
            mouse: bool = True,
            size: tuple[int, int] | None = None,
        ) -> None:
            super().__init__(app, debug=debug, mouse=mouse, size=size)
            self._file = sys.__stdout__

    globals()["StdoutLinuxDriver"] = StdoutLinuxDriver


async def run_with_tui() -> int:
    """Run the evaluation with Textual TUI and interactive approvals.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    _ensure_stdout_textual_driver()
    from llm_do.ui.app import LlmDoApp

    app: LlmDoApp | None = None

    # Set up queues for render pipeline and app communication
    render_queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    tui_event_queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    approval_queue: asyncio.Queue[ApprovalDecision] = asyncio.Queue()

    tui_backend = TextualDisplayBackend(tui_event_queue)

    # Container for result and exit code
    worker_result: list[Any] = []
    worker_exit_code: list[int] = [0]

    def on_event(event: UIEvent) -> None:
        """Forward events to the render pipeline."""
        render_queue.put_nowait(event)

    async def render_loop() -> None:
        """Render UI events through the TUI backend."""
        await tui_backend.start()
        try:
            while True:
                event = await render_queue.get()
                if event is None:
                    tui_event_queue.put_nowait(None)
                    render_queue.task_done()
                    break
                tui_backend.display(event)
                render_queue.task_done()
        finally:
            await tui_backend.stop()

    async def prompt_approval(request: ApprovalRequest) -> ApprovalDecision:
        """Send an approval request to the TUI and await the user's decision."""
        approval_event = parse_approval_request(request)
        render_queue.put_nowait(approval_event)
        return await approval_queue.get()

    approval_policy = RunApprovalPolicy(
        mode=APPROVAL_MODE,
        approval_callback=prompt_approval,
        return_permission_errors=True,
    )

    runtime = Runtime(
        cli_model=MODEL,
        run_approval_policy=approval_policy,
        on_event=on_event,
        verbosity=VERBOSITY,
    )

    entrypoint = build_entry([], [str(Path(__file__).resolve())])

    async def run_worker() -> int:
        """Run the worker and send events to the app."""
        try:
            result, _ctx = await runtime.run_invocable(
                entrypoint,
                WorkerInput(input=""),
                model=MODEL,
            )
            worker_result[:] = [result]
        except Exception as e:
            print(f"Error: {e}", file=sys.__stderr__)
            worker_exit_code[0] = 1
        finally:
            render_queue.put_nowait(None)
        return worker_exit_code[0]

    # Create the Textual app
    app = LlmDoApp(
        tui_event_queue,
        approval_queue,
        worker_coro=run_worker(),
        auto_quit=True,
    )

    # Run with mouse disabled to allow terminal text selection
    render_task = asyncio.create_task(render_loop())
    await app.run_async(mouse=False)
    render_queue.put_nowait(None)
    if not render_task.done():
        await render_task

    # Print final result to stdout
    if worker_result:
        print(worker_result[0])

    return worker_exit_code[0]


def cli_main():
    """Main entry point."""
    print(f"Starting TUI with MODEL={MODEL}, APPROVAL_MODE={APPROVAL_MODE}")
    print(f"Input directory: {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("-" * 60)

    exit_code = asyncio.run(run_with_tui())
    sys.exit(exit_code)


if __name__ == "__main__":
    cli_main()
