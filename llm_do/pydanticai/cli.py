"""CLI entry point for running PydanticAI-style workers.

The CLI is intentionally lightweight so it can be layered on top of the core
runtime without adding new dependencies. A mock agent runner is provided to
support deterministic tests and scripted replies without requiring a live LLM.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .base import AgentRunner, WorkerCreationProfile, WorkerRegistry, run_worker


def _load_jsonish(value: str) -> Any:
    """Load JSON from an inline string or filesystem path.

    The helper mirrors the permissive behavior of many CLIs: if the argument
    points to an existing file, the file is read as JSON. Otherwise the value
    itself is parsed as JSON. This keeps the interface small while supporting
    both ad-hoc invocations and scripted runs.
    """

    candidate = Path(value)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(value)


def _load_profile(path: Optional[str]) -> WorkerCreationProfile:
    if not path:
        return WorkerCreationProfile()
    data = _load_jsonish(path)
    return WorkerCreationProfile.model_validate(data)


def _build_mock_runner(reply: Any) -> AgentRunner:
    """Return an agent runner that uses a pre-registered reply.

    If *reply* is a mapping, the worker name is used to select a response with
    a per-worker fallback to the top-level structure. Otherwise the reply is
    returned verbatim. When an output schema is provided, the payload is
    validated before being returned so that CLI usage mirrors real integrations
    that honor worker schemas.
    """

    def _runner(definition, user_input, context, output_model):  # type: ignore[override]
        payload = reply
        if isinstance(reply, Dict):
            payload = reply.get(definition.name, reply)
        if output_model is not None:
            return output_model.model_validate(payload)
        return payload

    return _runner


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a PydanticAI worker")
    parser.add_argument("worker", help="Name of the worker to execute")
    parser.add_argument(
        "--registry",
        type=Path,
        required=True,
        help="Path to the worker registry root",
    )
    parser.add_argument(
        "--input",
        dest="input_data",
        default="{}",
        help="JSON payload or path to JSON file for worker input",
    )
    parser.add_argument(
        "--model",
        dest="cli_model",
        default=None,
        help="Override the effective model for this run",
    )
    parser.add_argument(
        "--profile",
        dest="profile_path",
        default=None,
        help="Optional JSON profile file for creation defaults",
    )
    parser.add_argument(
        "--mock-reply",
        dest="mock_reply",
        default=None,
        help="Inline JSON or file path used to bypass live LLM calls",
    )
    parser.add_argument(
        "--attachments",
        nargs="*",
        default=None,
        help="Attachment file paths passed to the worker",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    registry = WorkerRegistry(args.registry)
    input_data = _load_jsonish(args.input_data)
    profile = _load_profile(args.profile_path)

    runner: Optional[AgentRunner]
    if args.mock_reply is not None:
        mock_payload = _load_jsonish(args.mock_reply)
        runner = _build_mock_runner(mock_payload)
    else:
        runner = None

    run_kwargs: Dict[str, Any] = dict(
        registry=registry,
        worker=args.worker,
        input_data=input_data,
        attachments=args.attachments,
        cli_model=args.cli_model,
        creation_profile=profile,
    )
    if runner is not None:
        run_kwargs["agent_runner"] = runner

    result = run_worker(**run_kwargs)

    serialized = result.model_dump(mode="json")
    indent = 2 if args.pretty else None
    json.dump(serialized, sys.stdout, indent=indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

