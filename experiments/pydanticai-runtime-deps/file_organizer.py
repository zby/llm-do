from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from logging_utils import event_stream_logger
from otel_utils import configure_trace_logging
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from runtime import AgentRuntime, AttachmentResolver, build_path_map

ROOT = Path(__file__).parent
PROMPTS_DIR = ROOT / "prompts"
INPUT_DIR = ROOT / "input"
DEFAULT_LIST_PATH = INPUT_DIR / "files.txt"
MOCK_LIST_PATH = "path/to/files.txt"


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


class FileRename(BaseModel):
    original: str
    proposed: str
    reason: str


class FileOrganizerOutput(BaseModel):
    items: list[FileRename]
    summary: str = Field(description="Overall assessment of the rename plan")


def build_agents(model_name: str) -> tuple[Agent[Any, str], Agent[Any, FileOrganizerOutput]]:
    orchestrator_instructions = load_text(PROMPTS_DIR / "file_orchestrator.txt")
    organizer_instructions = load_text(PROMPTS_DIR / "file_organizer.txt")

    file_organizer = Agent(
        model=model_name,
        deps_type=AgentRuntime,
        instructions=organizer_instructions,
        output_type=FileOrganizerOutput,
    )

    orchestrator = Agent(
        model=model_name,
        deps_type=AgentRuntime,
        instructions=orchestrator_instructions,
        output_type=str,
    )

    @orchestrator.tool(name="find_file_list_path")
    def find_file_list_path(ctx: RunContext[AgentRuntime]) -> str:
        return MOCK_LIST_PATH

    @orchestrator.tool(name="file_organizer")
    async def call_file_organizer(
        ctx: RunContext[AgentRuntime],
        file_list_path: str,
    ) -> dict[str, Any]:
        file_list = ctx.deps.load_binary(file_list_path)
        prompt = [
            f"Organize the files listed in {file_list.identifier}.",
            file_list,
        ]
        plan = await ctx.deps.call_agent(
            "file_organizer",
            prompt,
            ctx=ctx,
        )
        if isinstance(plan, BaseModel):
            return plan.model_dump()
        if isinstance(plan, dict):
            return plan
        return {"plan": plan}

    return orchestrator, file_organizer


def build_prompt() -> str:
    return "Organize the available files and summarize the rename plan."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PydanticAI deps-as-runtime file organizer example.",
    )
    parser.add_argument(
        "--model",
        help="Model name (e.g. openai:gpt-4o-mini). Defaults to LLM_DO_MODEL.",
    )
    parser.add_argument(
        "--files",
        help=f"Path to file list. Defaults to {DEFAULT_LIST_PATH}.",
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
    args = parse_args()
    model_name = args.model or os.environ.get("LLM_DO_MODEL")
    if not model_name:
        raise SystemExit(
            "No model configured. Pass --model or set LLM_DO_MODEL."
        )

    list_path = (Path(args.files) if args.files else DEFAULT_LIST_PATH).resolve()
    if not list_path.exists():
        raise SystemExit(f"File list not found: {list_path}")

    if args.trace_dir:
        trace_config = configure_trace_logging(
            args.trace_dir,
            run_name="file-organizer",
            include_content=True,
            include_binary_content=args.trace_binary,
        )
        Agent.instrument_all(trace_config.settings)
        print(f"Trace log: {trace_config.path}")

    orchestrator, file_organizer = build_agents(model_name)
    event_handler = event_stream_logger() if args.log_events else None
    runtime = AgentRuntime(
        agents={
            "orchestrator": orchestrator,
            "file_organizer": file_organizer,
        },
        attachment_resolver=AttachmentResolver(
            path_map=build_path_map({MOCK_LIST_PATH: list_path}),
            base_path=ROOT,
        ),
        event_stream_handler=event_handler,
        max_depth=args.max_depth,
    )

    toolsets = runtime.toolsets_for(orchestrator)
    result = orchestrator.run_sync(
        build_prompt(),
        deps=runtime,
        event_stream_handler=event_handler,
        toolsets=toolsets,
    )

    print(result.output)
    print("\nUsage:", result.usage())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
