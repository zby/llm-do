#!/usr/bin/env python
"""Run an LLM agent using a manifest-driven project configuration.

Usage:
    llm-do <project-dir> [prompt]
    llm-do project.json [prompt]
    llm-do project.json --input-json '{"input": "Your prompt"}'

The manifest path can be a JSON file or a directory containing project.json.
The manifest specifies runtime config, entry selection, and file paths.
CLI input (prompt or --input-json) overrides manifest entry.args when allowed.
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import sys
from pathlib import Path
from typing import Any, Callable

from pydantic_ai.messages import ModelMessagesTypeAdapter

from ..oauth import (
    get_oauth_provider_for_model_provider,
    resolve_oauth_overrides,
)
from ..project import (
    AgentRegistry,
    ProjectManifest,
    build_registry,
    build_registry_host_wiring,
    load_manifest,
    load_module,
    resolve_entry,
    resolve_generated_agents_dir,
    resolve_manifest_paths,
)
from ..runtime import Entry
from ..ui import HeadlessDisplayBackend
from ..ui.runner import RunConfig, run_ui


def _input_to_args(data: dict[str, Any] | str) -> dict[str, Any]:
    """Convert CLI input (dict or string) to a dict for runtime validation."""
    if isinstance(data, str):
        return {"input": data}
    if not isinstance(data, dict):
        raise TypeError(f"Input must be str or dict, got {type(data)}")
    return dict(data)


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




def _load_init_modules(module_paths: list[str], manifest_dir: Path) -> None:
    """Load Python modules for side effects (e.g., custom provider registration)."""
    # TEMPORARY: Escape hatch for provider injection during CLI runs;
    # replace with a first-class manifest/runtime mechanism.
    for module_path in module_paths:
        path = Path(module_path)
        if not path.is_absolute():
            path = (manifest_dir / path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Init module not found: {module_path} (resolved: {path})")
        load_module(path)


def _make_entry_factory(
    manifest: ProjectManifest,
    manifest_dir: Path,
) -> Callable[[], tuple[Entry, AgentRegistry]]:
    def factory() -> tuple[Entry, AgentRegistry]:
        agent_paths, python_paths = resolve_manifest_paths(manifest, manifest_dir)
        registry = build_registry(
            [str(p) for p in agent_paths],
            [str(p) for p in python_paths],
            project_root=manifest_dir,
            **build_registry_host_wiring(manifest_dir),
        )
        entry = resolve_entry(
            manifest.entry,
            registry,
            python_files=python_paths,
            base_path=manifest_dir,
        )
        return entry, registry

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
        help="Prompt for the LLM (overrides manifest entry.args)",
    )
    parser.add_argument(
        "--input-json",
        dest="input_json",
        help="Input as inline JSON (overrides manifest entry.args)",
    )
    parser.add_argument(
        "--init-python",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "Load a Python module for side effects before building the registry "
            "(temporary provider injection path, e.g., register_model_factory). Repeatable."
        ),
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

    try:
        _load_init_modules(args.init_python, manifest_dir)
    except (FileNotFoundError, ImportError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
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
    elif manifest.entry.args is not None:
        raw_input = manifest.entry.args
    else:
        # Try reading from stdin if not a TTY
        if not sys.stdin.isatty():
            stdin_input = sys.stdin.read().strip()
            if stdin_input:
                raw_input = stdin_input
            else:
                print(
                    "Error: No input provided (use prompt argument, --input-json, or manifest entry.args)",
                    file=sys.stderr,
                )
                return 1
        else:
            print(
                "Error: No input provided (use prompt argument, --input-json, or manifest entry.args)",
                file=sys.stderr,
            )
            return 1

    # Convert to dict input for runtime validation
    try:
        input_data = _input_to_args(raw_input)
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
    log_verbosity = args.verbose
    message_log_callback = None
    if log_verbosity >= 3:
        message_log_callback = _make_message_log_callback(sys.stderr)

    backends: list[Any] = []
    extra_backends: list[Any] | None = None
    if 0 < log_verbosity < 3:
        backend = HeadlessDisplayBackend(sys.stderr, verbosity=log_verbosity)
        if use_tui:
            extra_backends = [backend]
        else:
            backends = [backend]

    run_verbosity = args.verbose
    if use_tui and run_verbosity == 0:
        run_verbosity = 1

    error_stream = sys.stderr if use_tui and extra_backends is None else None
    return_permission_errors = True if use_tui else manifest.runtime.return_permission_errors

    config = RunConfig(
        entry_factory=entry_factory,
        project_root=manifest_dir,
        approval_mode=manifest.runtime.approval_mode,
        auth_mode=manifest.runtime.auth_mode,
        verbosity=run_verbosity,
        return_permission_errors=return_permission_errors,
        max_depth=manifest.runtime.max_depth,
        generated_agents_dir=generated_agents_dir,
        agent_calls_require_approval=manifest.runtime.agent_calls_require_approval,
        agent_attachments_require_approval=manifest.runtime.agent_attachments_require_approval,
        agent_approval_overrides=manifest.runtime.agent_approval_overrides,
        oauth_provider_resolver=get_oauth_provider_for_model_provider,
        oauth_override_resolver=resolve_oauth_overrides,
        message_log_callback=message_log_callback,
        debug=args.debug,
        error_stream=error_stream,
    )
    outcome = asyncio.run(run_ui(
        input=input_data,
        config=config,
        mode="tui" if use_tui else "headless",
        backends=backends,
        extra_backends=extra_backends,
        chat=args.chat,
        agent_name="agent",
    ))
    if outcome.result is not None:
        print(outcome.result)
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(main())
