from __future__ import annotations

import asyncio

import pytest

from llm_do.ui.controllers import WorkerRunner


@pytest.mark.anyio
async def test_worker_runner_updates_message_history() -> None:
    async def run_turn(prompt: str, history: list[object] | None) -> list[object] | None:
        assert prompt == "hello"
        assert history is None
        return ["m1"]

    runner = WorkerRunner(run_turn=run_turn)
    task = runner.start_turn_task("hello")
    assert runner.is_running() is True
    await task
    assert runner.is_running() is False
    assert runner.message_history == ["m1"]


@pytest.mark.anyio
async def test_worker_runner_rejects_concurrent_turns() -> None:
    gate = asyncio.Event()

    async def run_turn(_: str, __: list[object] | None) -> list[object] | None:
        await gate.wait()
        return ["done"]

    runner = WorkerRunner(run_turn=run_turn)
    task = runner.start_turn_task("first")
    with pytest.raises(RuntimeError, match="already running"):
        runner.start_turn_task("second")

    gate.set()
    await task

