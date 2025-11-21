import json
import os
import subprocess
import sys
from pathlib import Path

from llm_do.pydanticai import WorkerDefinition, WorkerRegistry


def _run_cli(tmp_path: Path, args: list[str]) -> dict:
    command = [sys.executable, "-m", "llm_do.pydanticai.cli", *args]
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(Path(__file__).resolve().parents[1]))
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    return json.loads(completed.stdout)


def _setup_worker(tmp_path: Path, name: str) -> Path:
    registry_root = tmp_path / "workers"
    registry = WorkerRegistry(registry_root)
    registry.save_definition(WorkerDefinition(name=name, instructions="demo"))
    return registry_root


def test_cli_runs_with_mock_reply(tmp_path):
    registry_root = _setup_worker(tmp_path, "alpha")
    reply_file = tmp_path / "reply.json"
    reply_file.write_text(json.dumps({"ok": True}), encoding="utf-8")

    result = _run_cli(
        tmp_path,
        [
            "alpha",
            "--registry",
            str(registry_root),
            "--mock-reply",
            str(reply_file),
            "--input",
            json.dumps({"task": "demo"}),
        ],
    )

    assert result["output"] == {"ok": True}
    assert result["deferred_requests"] == []


def test_cli_supports_per_worker_reply_map(tmp_path):
    registry_root = _setup_worker(tmp_path, "beta")
    reply_map = {"beta": {"answer": 42}, "fallback": {"answer": 0}}
    reply_file = tmp_path / "reply_map.json"
    reply_file.write_text(json.dumps(reply_map), encoding="utf-8")

    result = _run_cli(
        tmp_path,
        [
            "beta",
            "--registry",
            str(registry_root),
            "--mock-reply",
            str(reply_file),
        ],
    )

    assert result["output"] == reply_map["beta"]
    assert result["deferred_requests"] == []
