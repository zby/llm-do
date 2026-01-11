#!/usr/bin/env python
"""v2_direct_tui: Run pitch deck evaluation with the Textual TUI.

Run with:
    uv run experiments/inv/v2_direct/run_tui.py
    uv run -m experiments.inv.v2_direct.run_tui
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalRequest

from llm_do.runtime import RunApprovalPolicy, Runtime, Worker
from llm_do.toolsets.filesystem import FileSystemToolset
from llm_do.ui.app import LlmDoApp
from llm_do.ui.events import UIEvent
from llm_do.ui.parser import parse_approval_request

# =============================================================================
# CONFIGURATION - Edit these constants to experiment
# =============================================================================

# Model selection
MODEL = "anthropic:claude-haiku-4-5"
# MODEL = "openai:gpt-4o-mini"
# MODEL = "anthropic:claude-sonnet-4-20250514"

# Approval settings
APPROVAL_MODE = "prompt"  # Use "approve_all" to skip prompts, "reject_all" to deny.

# Verbosity: 0=quiet, 1=show tool calls, 2=stream responses
VERBOSITY = 1

# Prompt to send
PROMPT = "Go"

# Chat mode: keep the UI open for multi-turn prompts
CHAT_MODE = False

# =============================================================================
# Worker definitions
# =============================================================================

HERE = Path(__file__).parent


def load_instructions(name: str) -> str:
    """Load instructions from the instructions/ directory."""
    return (HERE / "instructions" / f"{name}.md").read_text()


def build_workers() -> tuple[Worker, Worker]:
    """Build and return the worker entries."""
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
# Runtime + TUI
# =============================================================================

async def run_tui() -> str:
    """Run the evaluation with the Textual TUI."""
    main, _pitch_evaluator = build_workers()
    event_queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    approval_queue: asyncio.Queue[ApprovalDecision] = asyncio.Queue()
    result_holder: list[str] = []

    def on_event(event: UIEvent) -> None:
        event_queue.put_nowait(event)

    async def prompt_approval(request: ApprovalRequest) -> ApprovalDecision:
        approval_event = parse_approval_request(request)
        event_queue.put_nowait(approval_event)
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

    async def run_turn(user_prompt: str, message_history: list[Any] | None) -> list[Any] | None:
        result, ctx = await runtime.run_invocable(
            main,
            {"input": user_prompt},
            message_history=message_history,
        )
        result_holder[:] = [result]
        return list(ctx.messages)

    async def run_worker_once() -> int:
        await run_turn(PROMPT, None)
        if not CHAT_MODE:
            event_queue.put_nowait(None)
        return 0

    app = LlmDoApp(
        event_queue,
        approval_queue,
        worker_coro=run_worker_once(),
        run_turn=run_turn if CHAT_MODE else None,
        auto_quit=not CHAT_MODE,
    )

    await app.run_async(mouse=False)
    return result_holder[0] if result_holder else ""


def main() -> None:
    """Main entry point."""
    print(
        f"Running TUI with MODEL={MODEL}, APPROVAL_MODE={APPROVAL_MODE}, "
        f"VERBOSITY={VERBOSITY}, CHAT_MODE={CHAT_MODE}",
        file=sys.stderr,
    )
    result = asyncio.run(run_tui())
    if result:
        print(result)


if __name__ == "__main__":
    main()
