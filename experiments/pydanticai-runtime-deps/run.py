from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from logging_utils import event_stream_logger
from otel_utils import configure_trace_logging
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from runtime import AgentRuntime

ROOT = Path(__file__).parent
PROMPTS_DIR = ROOT / "prompts"
INPUT_DIR = ROOT / "input"
DEFAULT_DECK_PATH = INPUT_DIR / "deck.txt"

# Will be set to the actual deck path at runtime
_deck_path: Path | None = None


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


class PitchEvaluation(BaseModel):
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    score: int = Field(ge=1, le=10)
    recommendations: list[str]


def build_agents(model_name: str) -> tuple[Agent[Any, str], Agent[Any, PitchEvaluation]]:
    orchestrator_instructions = load_text(PROMPTS_DIR / "orchestrator.txt")
    evaluator_instructions = load_text(PROMPTS_DIR / "pitch_evaluator.txt")

    pitch_evaluator = Agent(
        model=model_name,
        deps_type=AgentRuntime,
        instructions=evaluator_instructions,
        output_type=PitchEvaluation,
    )

    orchestrator = Agent(
        model=model_name,
        deps_type=AgentRuntime,
        instructions=orchestrator_instructions,
        output_type=str,
    )

    @orchestrator.tool(name="find_deck_path")
    def find_deck_path(ctx: RunContext[AgentRuntime]) -> str:
        if _deck_path is None:
            raise RuntimeError("Deck path not configured")
        return str(_deck_path)

    @orchestrator.tool(name="pitch_evaluator")
    async def call_pitch_evaluator(
        ctx: RunContext[AgentRuntime],
        deck_path: str,
    ) -> dict[str, Any]:
        # Read text file content directly (Attachment is for binary files like images/PDFs)
        deck_content = Path(deck_path).read_text(encoding="utf-8")
        prompt = f"Analyze the following pitch deck:\n\n{deck_content}"
        evaluation = await ctx.deps.call_agent(
            "pitch_evaluator",
            prompt,
            ctx=ctx,
        )
        if isinstance(evaluation, BaseModel):
            return evaluation.model_dump()
        if isinstance(evaluation, dict):
            return evaluation
        return {"evaluation": evaluation}

    return orchestrator, pitch_evaluator


def build_prompt() -> str:
    return "Evaluate the available pitch deck and produce an investor summary."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PydanticAI delegation prototype using deps as runtime.",
    )
    parser.add_argument(
        "--model",
        help="Model name (e.g. openai:gpt-4o-mini). Defaults to LLM_DO_MODEL.",
    )
    parser.add_argument(
        "--deck",
        help=f"Path to deck text. Defaults to {DEFAULT_DECK_PATH}.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=5,
        help="Max delegation depth.",
    )
    parser.add_argument(
        "--log-events",
        action="store_true",
        help="Print every PydanticAI event.",
    )
    parser.add_argument(
        "--trace-dir",
        type=Path,
        help="Directory to write OpenTelemetry spans as JSONL.",
    )
    parser.add_argument(
        "--trace-binary",
        action="store_true",
        help="Include binary content in traces.",
    )
    return parser.parse_args()


def main() -> int:
    global _deck_path

    args = parse_args()
    model_name = args.model or os.environ.get("LLM_DO_MODEL")
    if not model_name:
        raise SystemExit(
            "No model configured. Pass --model or set LLM_DO_MODEL."
        )

    _deck_path = (Path(args.deck) if args.deck else DEFAULT_DECK_PATH).resolve()
    if not _deck_path.exists():
        raise SystemExit(f"Deck file not found: {_deck_path}")

    if args.trace_dir:
        trace_config = configure_trace_logging(
            args.trace_dir,
            run_name="pitchdeck",
            include_content=True,
            include_binary_content=args.trace_binary,
        )
        Agent.instrument_all(trace_config.settings)
        print(f"Trace log: {trace_config.path}")

    orchestrator, pitch_evaluator = build_agents(model_name)
    event_handler = event_stream_logger() if args.log_events else None
    runtime = AgentRuntime(
        agents={
            "orchestrator": orchestrator,
            "pitch_evaluator": pitch_evaluator,
        },
        base_path=ROOT,
        event_stream_handler=event_handler,
        max_depth=args.max_depth,
    )

    prompt = build_prompt()
    toolsets = runtime.toolsets_for(orchestrator)
    result = orchestrator.run_sync(
        prompt,
        deps=runtime,
        event_stream_handler=event_handler,
        toolsets=toolsets,
    )

    print(result.output)
    print("\nUsage:", result.usage())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
