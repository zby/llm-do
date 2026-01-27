#!/usr/bin/env python
"""Run an LLM agent using a manifest-driven project configuration.

Usage:
    llm-do <project-dir> [prompt]
    llm-do project.json [prompt]
    llm-do project.json --input-json '{"input": "Your prompt"}'

The manifest path can be a JSON file or a directory containing project.json.
The manifest specifies runtime config and file paths; the entry is resolved
from the file set (agent marked `entry: true` or a single `FunctionEntry` in Python).
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
    AgentRegistry,
    ApprovalCallback,
    Attachment,
    CallContext,
    Entry,
    EventCallback,
    PromptContent,
    RunApprovalPolicy,
    Runtime,
    build_entry,
)
from ..runtime.manifest import (
    ProjectManifest,
    load_manifest,
    resolve_generated_agents_dir,
    resolve_manifest_paths,
)
from ..ui import HeadlessDisplayBackend, run_headless, run_tui


def _input_to_messages(data: dict[str, Any] | str) -> list[PromptContent]:
    """Convert CLI input (dict or string) to a message list."""
    if isinstance(data, str):
        return [data]
    if not isinstance(data, dict):
        raise TypeError(f"Input must be str or dict, got {type(data)}")
    if "input" not in data:
        raise ValueError("Dict input must have an 'input' field")
    messages: list[PromptContent] = [data["input"]]
    for path in data.get("attachments") or []:
        messages.append(Attachment(path))
    return messages


def _make_message_log_callback(stream: Any) -> Callable[[str, int, list[Any]], None]:
    """Stream raw model request/response messages as JSONL."""
    counter = itertools.count()

    def callback(agent: str, depth: int, messages: list[Any]) -> None:
        try:
            serialized = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
        except Exception:
            serialized = []
            for msg in messages:
                try:
                    serialized.append(ModelMessagesTypeAdapter.dump_python([msg], mode="json")[0])
                except Exception:
                    serialized.append({"repr": repr(msg)})

        for message in serialized:
            record = {
                "seq": next(counter),
                "agent": agent,
                "depth": depth,
                "message": message,
            }
            stream.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
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
    entry: Entry | None = None,
    agent_registry: AgentRegistry | None = None,
    runtime: Runtime | None = None,
) -> tuple[Any, CallContext]:
    """Load entries from manifest and run with the given input.

    Args:
        manifest: The validated project manifest
        manifest_dir: Directory containing the manifest file
        input_data: Input data for the entry point
        on_event: Optional callback for runtime events (tool calls, streaming text)
        verbosity: Verbosity level (0=quiet, 1=progress, 2=streaming)
        approval_callback: Optional interactive approval callback (TUI mode)
        approval_cache: Optional shared cache for remember="session" approvals
        message_history: Optional prior messages for multi-turn conversations
        entry: Optional pre-built entry (skips entry build if provided)
        runtime: Optional pre-built runtime (skips approval/UI wiring if provided)

    Returns:
        Tuple of (result, context)
    """
    # Resolve file paths relative to manifest directory
    agent_paths, python_paths = resolve_manifest_paths(manifest, manifest_dir)

    if entry is None:
        entry, agent_registry = build_entry(
            [str(p) for p in agent_paths],
            [str(p) for p in python_paths],
            project_root=manifest_dir,
        )

    generated_agents_dir = resolve_generated_agents_dir(manifest, manifest_dir)
    if runtime is None:
        approval_mode: Literal["prompt", "approve_all", "reject_all"] = manifest.runtime.approval_mode

        approval_policy = RunApprovalPolicy(
            mode=approval_mode,
            approval_callback=approval_callback,
            cache=approval_cache,
            return_permission_errors=manifest.runtime.return_permission_errors,
        )
        message_log_callback = None
        if verbosity >= 3:
            message_log_callback = _make_message_log_callback(sys.stderr)
        runtime = Runtime(
            project_root=manifest_dir,
            run_approval_policy=approval_policy,
            max_depth=manifest.runtime.max_depth,
            generated_agents_dir=generated_agents_dir,
            agent_calls_require_approval=manifest.runtime.agent_calls_require_approval,
            agent_attachments_require_approval=manifest.runtime.agent_attachments_require_approval,
            agent_approval_overrides=manifest.runtime.agent_approval_overrides,
            on_event=on_event,
            message_log_callback=message_log_callback,
            verbosity=verbosity,
        )
        if agent_registry is not None:
            runtime.register_registry(agent_registry)
    else:
        if (
            approval_callback is not None
            or approval_cache is not None
            or on_event is not None
            or verbosity != 0
        ):
            raise ValueError("runtime provided; do not pass approval/UI overrides")
        if agent_registry is not None:
            runtime.register_registry(agent_registry)

    return await runtime.run_entry(
        entry,
        input_data,
        message_history=message_history,
    )


def _make_entry_factory(
    manifest: ProjectManifest,
    manifest_dir: Path,
) -> Callable[[], tuple[Entry, AgentRegistry]]:
    def factory() -> tuple[Entry, AgentRegistry]:
        agent_paths, python_paths = resolve_manifest_paths(manifest, manifest_dir)
        return build_entry(
            [str(p) for p in agent_paths],
            [str(p) for p in python_paths],
            project_root=manifest_dir,
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
        "-v", "--verbose",
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

    args = parser.parse_intermixed_args()

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

    # Build input as message list from CLI or manifest
    raw_input: dict[str, Any] | str | None = None
    if args.input_json is not None:
        try:
            raw_input = json.loads(args.input_json)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --input-json: {e}", file=sys.stderr)
            return 1
        if not isinstance(raw_input, dict):
            print("Error: --input-json must be a JSON object", file=sys.stderr)
            return 1
    elif args.prompt is not None:
        raw_input = args.prompt
    elif manifest.entry.input is not None:
        raw_input = manifest.entry.input
    else:
        # Try reading from stdin if not a TTY
        if not sys.stdin.isatty():
            stdin_input = sys.stdin.read().strip()
            if stdin_input:
                raw_input = stdin_input
            else:
                print(
                    "Error: No input provided (use prompt argument, --input-json, or manifest entry.input)",
                    file=sys.stderr,
                )
                return 1
        else:
            print(
                "Error: No input provided (use prompt argument, --input-json, or manifest entry.input)",
                file=sys.stderr,
            )
            return 1

    # Convert to message list (canonical internal format)
    try:
        input_messages = _input_to_messages(raw_input)
    except (TypeError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    entry_factory = _make_entry_factory(manifest, manifest_dir)

    # Determine if we should use TUI mode:
    # - Explicit --tui flag
    # - Or: TTY available and not --headless
    use_tui = args.tui or (sys.stdout.isatty() and not args.headless)

    # TUI mode
    if args.chat and not use_tui:
        print("Chat mode requires TUI (--tui or a TTY).", file=sys.stderr)
        return 1

    generated_agents_dir = resolve_generated_agents_dir(manifest, manifest_dir)
    if use_tui:
        tui_verbosity = args.verbose if args.verbose > 0 else 1
        log_verbosity = args.verbose
        message_log_callback = None
        if log_verbosity >= 3:
            message_log_callback = _make_message_log_callback(sys.stderr)

        extra_backends = None
        if 0 < log_verbosity < 3:
            extra_backends = [HeadlessDisplayBackend(sys.stderr, verbosity=log_verbosity)]

        error_stream = sys.stderr if extra_backends is None else None
        # Extract text for initial prompt display
        initial_prompt = next((m for m in input_messages if isinstance(m, str)), "")
        outcome = asyncio.run(run_tui(
            input=input_messages,
            entry_factory=entry_factory,
            project_root=manifest_dir,
            approval_mode=manifest.runtime.approval_mode,
            verbosity=tui_verbosity,
            return_permission_errors=True,
            max_depth=manifest.runtime.max_depth,
            generated_agents_dir=generated_agents_dir,
            agent_calls_require_approval=manifest.runtime.agent_calls_require_approval,
            agent_attachments_require_approval=manifest.runtime.agent_attachments_require_approval,
            agent_approval_overrides=manifest.runtime.agent_approval_overrides,
            message_log_callback=message_log_callback,
            extra_backends=extra_backends,
            chat=args.chat,
            initial_prompt=initial_prompt,
            debug=args.debug,
            agent_name="agent",
            error_stream=error_stream,
        ))
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

    outcome = asyncio.run(run_headless(
        input=input_messages,
        entry_factory=entry_factory,
        project_root=manifest_dir,
        approval_mode=manifest.runtime.approval_mode,
        verbosity=args.verbose,
        return_permission_errors=manifest.runtime.return_permission_errors,
        max_depth=manifest.runtime.max_depth,
        generated_agents_dir=generated_agents_dir,
        agent_calls_require_approval=manifest.runtime.agent_calls_require_approval,
        agent_attachments_require_approval=manifest.runtime.agent_attachments_require_approval,
        agent_approval_overrides=manifest.runtime.agent_approval_overrides,
        backends=backends,
        message_log_callback=message_log_callback,
        debug=args.debug,
    ))
    if outcome.result is not None:
        print(outcome.result)
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(main())
