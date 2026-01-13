"""Helpers for running entries with TUI or headless UI."""
from __future__ import annotations

import asyncio
import os
import sys
import traceback
from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalRequest

from llm_do.runtime import Entry, ModelType, RunApprovalPolicy, Runtime

from .display import HeadlessDisplayBackend, TextualDisplayBackend
from .events import ErrorEvent, UIEvent
from .parser import parse_approval_request

UiMode = Literal["tui", "headless"]
ApprovalMode = Literal["prompt", "approve_all", "reject_all"]
EventSink = Callable[[UIEvent], None]


@dataclass(frozen=True, slots=True)
class RunUiResult:
    """Result from a UI run."""

    result: Any | None
    exit_code: int


def _ensure_stdout_textual_driver() -> None:
    """Configure Textual to write TUI output to stdout on Linux."""
    if sys.platform.startswith("win"):
        return
    if os.environ.get("TEXTUAL_DRIVER"):
        return

    os.environ["TEXTUAL_DRIVER"] = f"{__name__}:StdoutLinuxDriver"

    from textual.drivers.linux_driver import LinuxDriver

    class StdoutLinuxDriver(LinuxDriver):
        def __init__(
            self,
            app: Any,
            *,
            debug: bool = False,
            mouse: bool = True,
            size: tuple[int, int] | None = None,
        ) -> None:
            super().__init__(app, debug=debug, mouse=mouse, size=size)
            self._file = sys.__stdout__

    globals()["StdoutLinuxDriver"] = StdoutLinuxDriver


def _format_exception_message(exc: BaseException) -> str:
    message = str(exc)
    return message if message else repr(exc)


def _emit_error(
    sink: EventSink,
    *,
    worker: str,
    message: str,
    error_type: str,
    traceback_text: str | None,
) -> None:
    sink(ErrorEvent(
        worker=worker,
        message=message,
        error_type=error_type,
        traceback=traceback_text,
    ))


async def run_tui(
    *,
    entry: Entry,
    input: Any,
    model: ModelType | None = None,
    approval_mode: ApprovalMode = "prompt",
    verbosity: int = 1,
    return_permission_errors: bool = True,
) -> RunUiResult:
    """Run a single entry with the Textual TUI."""
    _ensure_stdout_textual_driver()
    from .app import LlmDoApp

    tui_event_queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    approval_queue: asyncio.Queue[ApprovalDecision] = asyncio.Queue()
    tui_backend = TextualDisplayBackend(tui_event_queue)
    entry_name = getattr(entry, "name", "worker")

    def on_event(event: UIEvent) -> None:
        tui_backend.display(event)

    async def prompt_approval(request: ApprovalRequest) -> ApprovalDecision:
        approval_event = parse_approval_request(request)
        tui_backend.display(approval_event)
        return await approval_queue.get()

    approval_callback = prompt_approval if approval_mode == "prompt" else None
    approval_policy = RunApprovalPolicy(
        mode=approval_mode,
        approval_callback=approval_callback,
        return_permission_errors=return_permission_errors,
    )

    runtime = Runtime(
        cli_model=model,
        run_approval_policy=approval_policy,
        on_event=on_event,
        verbosity=verbosity,
    )

    result_holder: list[Any] = []
    exit_code = 0

    async def run_worker() -> int:
        nonlocal exit_code
        try:
            result, _ctx = await runtime.run_entry(entry, input, model=model)
            result_holder[:] = [result]
        except KeyboardInterrupt:
            exit_code = 1
            traceback_text = traceback.format_exc() if verbosity >= 2 else None
            _emit_error(
                on_event,
                worker=entry_name,
                message="Aborted by user",
                error_type="KeyboardInterrupt",
                traceback_text=traceback_text,
            )
        except Exception as exc:
            exit_code = 1
            traceback_text = traceback.format_exc() if verbosity >= 2 else None
            _emit_error(
                on_event,
                worker=entry_name,
                message=_format_exception_message(exc),
                error_type=type(exc).__name__,
                traceback_text=traceback_text,
            )
        finally:
            tui_event_queue.put_nowait(None)
        return exit_code

    app = LlmDoApp(
        tui_event_queue,
        approval_queue,
        worker_coro=run_worker(),
        auto_quit=True,
    )

    await app.run_async(mouse=False)
    result = result_holder[0] if result_holder else None
    return RunUiResult(result=result, exit_code=exit_code)


async def run_headless(
    *,
    entry: Entry,
    input: Any,
    model: ModelType | None = None,
    approval_mode: ApprovalMode = "approve_all",
    verbosity: int = 1,
    return_permission_errors: bool = True,
) -> RunUiResult:
    """Run a single entry with a headless text backend."""
    if approval_mode == "prompt":
        raise ValueError("Headless mode cannot prompt for approvals; use approve_all or reject_all.")

    backend = HeadlessDisplayBackend(stream=sys.stderr, verbosity=verbosity)
    await backend.start()

    def on_event(event: UIEvent) -> None:
        backend.display(event)

    approval_policy = RunApprovalPolicy(
        mode=approval_mode,
        return_permission_errors=return_permission_errors,
    )

    runtime = Runtime(
        cli_model=model,
        run_approval_policy=approval_policy,
        on_event=on_event,
        verbosity=verbosity,
    )

    result: Any | None = None
    exit_code = 0
    entry_name = getattr(entry, "name", "worker")

    try:
        result, _ctx = await runtime.run_entry(entry, input, model=model)
    except KeyboardInterrupt:
        exit_code = 1
        traceback_text = traceback.format_exc() if verbosity >= 2 else None
        _emit_error(
            on_event,
            worker=entry_name,
            message="Aborted by user",
            error_type="KeyboardInterrupt",
            traceback_text=traceback_text,
        )
    except Exception as exc:
        exit_code = 1
        traceback_text = traceback.format_exc() if verbosity >= 2 else None
        _emit_error(
            on_event,
            worker=entry_name,
            message=_format_exception_message(exc),
            error_type=type(exc).__name__,
            traceback_text=traceback_text,
        )
    finally:
        await backend.stop()

    return RunUiResult(result=result, exit_code=exit_code)


async def run_ui(
    *,
    entry: Entry,
    input: Any,
    mode: UiMode = "tui",
    model: ModelType | None = None,
    approval_mode: ApprovalMode = "prompt",
    verbosity: int = 1,
    return_permission_errors: bool = True,
) -> RunUiResult:
    """Run a single entry with either TUI or headless UI."""
    if mode == "tui":
        return await run_tui(
            entry=entry,
            input=input,
            model=model,
            approval_mode=approval_mode,
            verbosity=verbosity,
            return_permission_errors=return_permission_errors,
        )
    if mode == "headless":
        return await run_headless(
            entry=entry,
            input=input,
            model=model,
            approval_mode=approval_mode,
            verbosity=verbosity,
            return_permission_errors=return_permission_errors,
        )
    raise ValueError(f"Unknown UI mode: {mode}")
