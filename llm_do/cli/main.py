#!/usr/bin/env python
"""Run an LLM worker using a manifest-driven project configuration.

Usage:
    llm-do <project-dir> [prompt]
    llm-do project.json [prompt]
    llm-do project.json --input-json '{"input": "Your prompt"}'

The manifest path can be a JSON file or a directory containing project.json.
The manifest specifies runtime config and file paths; the entry is resolved
from the file set (worker marked `entry: true`).
CLI input (prompt or --input-json) overrides manifest entry.input when allowed.
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import sys
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai_blocking_approval import ApprovalDecision

from ..runtime import (
    AgentBundle,
    AgentRuntime,
    ApprovalCallback,
    AttachmentResolver,
    EventCallback,
    RunApprovalPolicy,
    load_agents,
)
from ..runtime.executor import build_runtime, run_entry_agent
from ..runtime.manifest import (
    ProjectManifest,
    load_manifest,
    resolve_manifest_paths,
)
from ..ui import HeadlessDisplayBackend, run_headless, run_tui


def _make_message_log_callback(stream: Any) -> Callable[[str, int, list[Any]], None]:
    """Stream raw model request/response messages as JSONL."""
    counter = itertools.count()

    def callback(worker: str, depth: int, messages: list[Any]) -> None:
        try:
            serialized = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
        except Exception:
            serialized = []
            for msg in messages:
                try:
                    serialized.append(
                        ModelMessagesTypeAdapter.dump_python([msg], mode="json")[0]
                    )
                except Exception:
                    serialized.append({"repr": repr(msg)})

        for message in serialized:
            record = {
                "seq": next(counter),
                "worker": worker,
                "depth": depth,
                "message": message,
            }
            stream.write(json.dumps(record, ensure_ascii=True, indent=2) + "\n")
        stream.flush()

    return callback


async def run(
    manifest: ProjectManifest,
    manifest_dir: Path,
    input_data: dict[str, Any],
    *,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
    approval_callback: ApprovalCallback | None = None,
    approval_cache: dict[Any, ApprovalDecision] | None = None,
    message_history: list[Any] | None = None,
    bundle: AgentBundle | None = None,
    runtime: AgentRuntime | None = None,
) -> tuple[Any, AgentRuntime]:
    """Load agents from manifest and run with the given input.

    Args:
        manifest: The validated project manifest
        manifest_dir: Directory containing the manifest file
        input_data: Input data for the entry point
        on_event: Optional callback for runtime events (tool calls, streaming text)
        verbosity: Verbosity level (0=quiet, 1=progress, 2=streaming)
        approval_callback: Optional interactive approval callback (TUI mode)
        approval_cache: Optional shared cache for remember="session" approvals
        message_history: Optional prior messages for multi-turn conversations
        bundle: Optional pre-built agent bundle (skips loading if provided)
        runtime: Optional pre-built runtime (skips approval/UI wiring if provided)

    Returns:
        Tuple of (result, runtime)
    """
    # Resolve file paths relative to manifest directory
    worker_paths, python_paths = resolve_manifest_paths(manifest, manifest_dir)

    if bundle is None:
        bundle = load_agents(
            worker_paths,
            python_files=python_paths,
            project_root=manifest_dir,
            cwd=manifest_dir,
        )

    if runtime is None:
        approval_mode: Literal["prompt", "approve_all", "reject_all"] = (
            manifest.runtime.approval_mode
        )

        approval_policy = RunApprovalPolicy(
            mode=approval_mode,
            approval_callback=approval_callback,
            cache=approval_cache,
            return_permission_errors=manifest.runtime.return_permission_errors,
        )
        message_log_callback = None
        if verbosity >= 3:
            message_log_callback = _make_message_log_callback(sys.stderr)

        runtime = build_runtime(
            bundle,
            project_root=manifest_dir,
            approval_policy=approval_policy,
            max_depth=manifest.runtime.max_depth,
            on_event=on_event,
            message_log_callback=message_log_callback,
            verbosity=verbosity,
            return_permission_errors=manifest.runtime.return_permission_errors,
        )
    else:
        if (
            approval_callback is not None
            or approval_cache is not None
            or on_event is not None
            or verbosity != 0
        ):
            raise ValueError("runtime provided; do not pass approval/UI overrides")

    result = await run_entry_agent(bundle, input_data, runtime=runtime)
    return result, runtime


def _make_bundle_factory(
    manifest: ProjectManifest,
    manifest_dir: Path,
) -> Callable[[], AgentBundle]:
    """Create a factory function for loading agent bundles."""

    def factory() -> AgentBundle:
        worker_paths, python_paths = resolve_manifest_paths(manifest, manifest_dir)
        return load_agents(
            worker_paths,
            python_files=python_paths,
            project_root=manifest_dir,
            cwd=manifest_dir,
        )

    return factory


def main() -> int:
    """Main entry point for llm-do CLI.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "manifest",
        help="Path to project manifest (JSON file or directory containing project.json)",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Prompt for the LLM (overrides manifest entry.input)",
    )
    parser.add_argument(
        "--input-json",
        dest="input_json",
        help="Input as inline JSON (overrides manifest entry.input)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help=(
            "Show progress (-v for tool calls, -vv for streaming, "
            "-vvv for full LLM message log JSONL only)"
        ),
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Force headless mode (no TUI, plain text output)",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Force TUI mode (interactive UI)",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Enable multi-turn chat mode in the TUI",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show full tracebacks on error",
    )

    args = parser.parse_args()

    # Validate mutually exclusive flags
    if args.headless and args.tui:
        print("Cannot combine --headless and --tui", file=sys.stderr)
        return 1

    # Load and validate manifest
    try:
        manifest, manifest_dir = load_manifest(args.manifest)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1

    # Determine input data
    has_cli_input = args.prompt is not None or args.input_json is not None

    if has_cli_input and not manifest.allow_cli_input:
        print(
            "Error: CLI input not allowed by manifest (allow_cli_input is false)",
            file=sys.stderr,
        )
        return 1

    if args.prompt is not None and args.input_json is not None:
        print("Error: Cannot combine prompt argument and --input-json", file=sys.stderr)
        return 1

    # Build input_data from CLI or manifest
    input_data: dict[str, Any]
    if args.input_json is not None:
        try:
            input_data = json.loads(args.input_json)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --input-json: {e}", file=sys.stderr)
            return 1
        if not isinstance(input_data, dict):
            print("Error: --input-json must be a JSON object", file=sys.stderr)
            return 1
    elif args.prompt is not None:
        input_data = {"input": args.prompt}
    elif manifest.entry.input is not None:
        input_data = manifest.entry.input
    else:
        # Try reading from stdin if not a TTY
        if not sys.stdin.isatty():
            stdin_input = sys.stdin.read().strip()
            if stdin_input:
                input_data = {"input": stdin_input}
            else:
                print(
                    "Error: No input provided (use prompt argument, --input-json, "
                    "or manifest entry.input)",
                    file=sys.stderr,
                )
                return 1
        else:
            print(
                "Error: No input provided (use prompt argument, --input-json, "
                "or manifest entry.input)",
                file=sys.stderr,
            )
            return 1

    bundle_factory = _make_bundle_factory(manifest, manifest_dir)

    # Determine if we should use TUI mode:
    # - Explicit --tui flag
    # - Or: TTY available and not --headless
    use_tui = args.tui or (sys.stdout.isatty() and not args.headless)

    # TUI mode
    if args.chat and not use_tui:
        print("Chat mode requires TUI (--tui or a TTY).", file=sys.stderr)
        return 1

    if use_tui:
        tui_verbosity = args.verbose if args.verbose > 0 else 1
        log_verbosity = args.verbose
        message_log_callback = None
        if log_verbosity >= 3:
            message_log_callback = _make_message_log_callback(sys.stderr)

        extra_backends = None
        if 0 < log_verbosity < 3:
            extra_backends = [
                HeadlessDisplayBackend(sys.stderr, verbosity=log_verbosity)
            ]

        error_stream = sys.stderr if extra_backends is None else None
        initial_prompt = (
            input_data.get("input", "") if isinstance(input_data, dict) else ""
        )
        outcome = asyncio.run(
            run_tui(
                input=input_data,
                entry_factory=bundle_factory,
                project_root=manifest_dir,
                approval_mode=manifest.runtime.approval_mode,
                verbosity=tui_verbosity,
                return_permission_errors=True,
                max_depth=manifest.runtime.max_depth,
                worker_calls_require_approval=manifest.runtime.worker_calls_require_approval,
                worker_attachments_require_approval=manifest.runtime.worker_attachments_require_approval,
                worker_approval_overrides=manifest.runtime.worker_approval_overrides,
                message_log_callback=message_log_callback,
                extra_backends=extra_backends,
                chat=args.chat,
                initial_prompt=initial_prompt,
                debug=args.debug,
                worker_name="worker",
                error_stream=error_stream,
            )
        )
        if outcome.result is not None:
            print(outcome.result)
        return outcome.exit_code

    # Headless mode: set up display backend based on flags
    backends: list[Any]
    if 0 < args.verbose < 3:
        backends = [HeadlessDisplayBackend(stream=sys.stderr, verbosity=args.verbose)]
    else:
        backends = []

    message_log_callback = None
    if args.verbose >= 3:
        message_log_callback = _make_message_log_callback(sys.stderr)

    outcome = asyncio.run(
        run_headless(
            input=input_data,
            entry_factory=bundle_factory,
            project_root=manifest_dir,
            approval_mode=manifest.runtime.approval_mode,
            verbosity=args.verbose,
            return_permission_errors=manifest.runtime.return_permission_errors,
            max_depth=manifest.runtime.max_depth,
            worker_calls_require_approval=manifest.runtime.worker_calls_require_approval,
            worker_attachments_require_approval=manifest.runtime.worker_attachments_require_approval,
            worker_approval_overrides=manifest.runtime.worker_approval_overrides,
            backends=backends,
            message_log_callback=message_log_callback,
            debug=args.debug,
        )
    )
    if outcome.result is not None:
        print(outcome.result)
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(main())
