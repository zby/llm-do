from __future__ import annotations

import argparse
import os
from pathlib import Path

from logging_utils import event_stream_logger
from otel_utils import configure_trace_logging
from runtime import AgentRuntime, AttachmentResolver, build_path_map
from worker_loader import load_worker_agents

DEFAULT_PROJECT_DIR = Path("examples/recursive_task_decomposer")
DEFAULT_INPUT_PATH = DEFAULT_PROJECT_DIR / "sample_input.txt"
DEFAULT_ENTRY = "main"


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recursive task decomposer via PydanticAI deps-as-runtime.",
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=DEFAULT_PROJECT_DIR,
        help=f"Project directory (default: {DEFAULT_PROJECT_DIR})",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"Input file (default: {DEFAULT_INPUT_PATH})",
    )
    parser.add_argument(
        "--model",
        help="Model name (e.g. openai:gpt-4o-mini). Defaults to LLM_DO_MODEL.",
    )
    parser.add_argument(
        "--entry",
        default=DEFAULT_ENTRY,
        help="Entry worker name (default: main).",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
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

    project_dir = args.project.resolve()
    input_path = args.input.resolve()
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    worker_files = [
        project_dir / "main.worker",
        project_dir / "planner.worker",
    ]

    if args.trace_dir:
        trace_config = configure_trace_logging(
            args.trace_dir,
            run_name="recursive-task-decomposer",
            include_content=True,
            include_binary_content=args.trace_binary,
        )
        from pydantic_ai import Agent

        Agent.instrument_all(trace_config.settings)
        print(f"Trace log: {trace_config.path}")

    bundle = load_worker_agents(
        worker_files=worker_files,
        model_override=model_name,
        project_root=project_dir,
        cwd=project_dir,
    )

    if bundle.unsupported_toolsets:
        print("Unsupported toolsets detected:")
        for name, toolsets in bundle.unsupported_toolsets.items():
            print(f"- {name}: {toolsets}")

    entry_name = args.entry or bundle.entry_name or DEFAULT_ENTRY
    entry_agent = bundle.agents.get(entry_name)
    if entry_agent is None:
        available = ", ".join(sorted(bundle.agents))
        raise SystemExit(f"Entry '{entry_name}' not found. Available: {available}")

    event_handler = event_stream_logger() if args.log_events else None
    runtime = AgentRuntime(
        agents=bundle.agents,
        toolset_specs=bundle.toolset_specs,
        toolset_registry=bundle.toolset_registry,
        attachment_resolver=AttachmentResolver(
            path_map=build_path_map({}),
            base_path=project_dir,
        ),
        event_stream_handler=event_handler,
        max_depth=args.max_depth,
    )

    prompt = load_text(input_path)
    toolsets = runtime.toolsets_for(entry_agent)
    result = entry_agent.run_sync(
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
