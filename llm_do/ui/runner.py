"""Helpers for running entries with TUI or headless UI."""
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence, TextIO

from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UserError
from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalRequest

from llm_do.runtime import Entry, RunApprovalPolicy, Runtime
from llm_do.runtime.contracts import MessageLogCallback
from llm_do.runtime.events import RuntimeEvent

from .adapter import adapt_event
from .display import DisplayBackend, HeadlessDisplayBackend, TextualDisplayBackend
from .events import UIEvent
from .parser import parse_approval_request

UiMode = Literal["tui", "headless"]
ApprovalMode = Literal["prompt", "approve_all", "reject_all"]
UiEventSink = Callable[[UIEvent], None]
RuntimeEventSink = Callable[[RuntimeEvent], None]
EntryFactory = Callable[[], Entry]
RuntimeFactory = Callable[..., Runtime]


@dataclass(frozen=True, slots=True)
class RunUiResult:
    result: Any | None
    exit_code: int


def _ensure_stdout_textual_driver() -> None:
    if sys.platform.startswith("win") or os.environ.get("TEXTUAL_DRIVER"):
        return
    os.environ["TEXTUAL_DRIVER"] = f"{__name__}:StdoutLinuxDriver"
    from textual.drivers.linux_driver import LinuxDriver

    class StdoutLinuxDriver(LinuxDriver):
        def __init__(self, app: Any, *, debug: bool = False, mouse: bool = True, size: tuple[int, int] | None = None) -> None:
            super().__init__(app, debug=debug, mouse=mouse, size=size)
            self._file = sys.__stdout__
    globals()["StdoutLinuxDriver"] = StdoutLinuxDriver


def _format_run_error_message(exc: BaseException) -> str:
    if isinstance(exc, ModelHTTPError):
        msg = f"Model API error (status {exc.status_code}): {exc.model_name}"
        if exc.body and isinstance(exc.body, dict) and isinstance(exc.body.get("error"), dict):
            detail = exc.body["error"].get("message", "")
            if detail:
                return f"{msg}\n  {detail}"
        return msg
    if isinstance(exc, (FileNotFoundError, ValueError, PermissionError, UnexpectedModelBehavior, UserError)):
        return f"Error: {exc}"
    if isinstance(exc, KeyboardInterrupt):
        return "Aborted by user"
    return f"Unexpected error: {exc}"


def _resolve_entry_factory(entry: Entry | None, entry_factory: EntryFactory | None) -> EntryFactory:
    if entry is not None and entry_factory is not None:
        raise ValueError("Provide either entry or entry_factory, not both.")
    if entry_factory is not None:
        return entry_factory
    if entry is None:
        raise ValueError("entry or entry_factory is required.")
    return lambda: entry


def _build_runtime(
    *,
    project_root: Path | None,
    run_approval_policy: RunApprovalPolicy,
    max_depth: int,
    worker_calls_require_approval: bool,
    worker_attachments_require_approval: bool,
    worker_approval_overrides: Mapping[str, Any] | None,
    on_event: RuntimeEventSink | None,
    message_log_callback: MessageLogCallback | None,
    verbosity: int,
    runtime_factory: RuntimeFactory | None,
) -> Runtime:
    factory = runtime_factory or Runtime
    return factory(
        project_root=project_root, run_approval_policy=run_approval_policy, max_depth=max_depth,
        worker_calls_require_approval=worker_calls_require_approval,
        worker_attachments_require_approval=worker_attachments_require_approval,
        worker_approval_overrides=worker_approval_overrides, on_event=on_event,
        message_log_callback=message_log_callback, verbosity=verbosity,
    )


async def _render_loop(
    queue: asyncio.Queue[UIEvent | None], backends: Sequence[DisplayBackend], *, on_close: Callable[[], None] | None = None
) -> None:
    for backend in backends:
        await backend.start()
    try:
        while True:
            event = await queue.get()
            if event is None:
                queue.task_done()
                break
            for backend in backends:
                backend.display(event)
            queue.task_done()
    finally:
        if on_close:
            on_close()
        for backend in backends:
            await backend.stop()


async def run_tui(
    *,
    input: Any,
    entry: Entry | None = None,
    entry_factory: EntryFactory | None = None,
    project_root: Path | None = None,
    approval_mode: ApprovalMode = "prompt",
    verbosity: int = 1,
    return_permission_errors: bool = True,
    max_depth: int = 5,
    worker_calls_require_approval: bool = False,
    worker_attachments_require_approval: bool = False,
    worker_approval_overrides: Mapping[str, Any] | None = None,
    message_log_callback: MessageLogCallback | None = None,
    extra_backends: Sequence[DisplayBackend] | None = None,
    chat: bool = False,
    initial_prompt: str | None = None,
    debug: bool = False,
    worker_name: str | None = None,
    runtime_factory: RuntimeFactory | None = None,
    error_stream: TextIO | None = None,
) -> RunUiResult:
    """Run a single entry with the Textual TUI."""
    _ensure_stdout_textual_driver()
    from .app import LlmDoApp

    entry_factory = _resolve_entry_factory(entry, entry_factory)
    app: LlmDoApp | None = None
    tui_event_queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    approval_queue: asyncio.Queue[ApprovalDecision] = asyncio.Queue()
    tui_backend = TextualDisplayBackend(tui_event_queue)
    entry_name = worker_name if worker_name is not None else str(getattr(entry, "name", "worker"))

    render_queue: asyncio.Queue[UIEvent | None] = asyncio.Queue()
    backends: list[DisplayBackend] = [tui_backend]
    if extra_backends:
        backends.extend(extra_backends)
    render_task = asyncio.create_task(
        _render_loop(
            render_queue,
            backends,
            on_close=lambda: tui_event_queue.put_nowait(None),
        )
    )
    render_closed = False

    def emit_ui_event(event: UIEvent) -> None:
        render_queue.put_nowait(event)

    def on_event(event: RuntimeEvent) -> None:
        render_queue.put_nowait(adapt_event(event))

    async def prompt_approval(request: ApprovalRequest) -> ApprovalDecision:
        approval_event = parse_approval_request(request)
        render_queue.put_nowait(approval_event)
        return await approval_queue.get()

    approval_callback = prompt_approval if approval_mode == "prompt" else None
    approval_policy = RunApprovalPolicy(
        mode=approval_mode,
        approval_callback=approval_callback,
        return_permission_errors=return_permission_errors,
    )

    runtime = _build_runtime(
        project_root=project_root,
        run_approval_policy=approval_policy,
        max_depth=max_depth,
        worker_calls_require_approval=worker_calls_require_approval,
        worker_attachments_require_approval=worker_attachments_require_approval,
        worker_approval_overrides=worker_approval_overrides,
        on_event=on_event,
        message_log_callback=message_log_callback,
        verbosity=verbosity,
        runtime_factory=runtime_factory,
    )

    result_holder: list[Any] = []
    exit_code = 0

    def emit_error(message: str, error_type: str) -> None:
        nonlocal exit_code
        if error_stream is not None:
            print(f"[{entry_name}] ERROR ({error_type}): {message}", file=error_stream, flush=True)
        from .events import ErrorEvent
        emit_ui_event(ErrorEvent(worker=entry_name, message=message, error_type=error_type))
        exit_code = 1

    async def run_entry(
        input_data: Any,
        message_history: list[Any] | None,
    ) -> list[Any] | None:
        entry_instance = entry_factory()
        result, ctx = await runtime.run_entry(
            entry_instance,
            input_data,
            message_history=message_history,
        )
        result_holder[:] = [result]
        return list(ctx.frame.messages)

    async def run_with_input(
        input_data: Any,
        message_history: list[Any] | None,
    ) -> list[Any] | None:
        try:
            return await run_entry(input_data, message_history)
        except KeyboardInterrupt as exc:
            emit_error(_format_run_error_message(exc), type(exc).__name__)
            return None
        except Exception as exc:
            emit_error(_format_run_error_message(exc), type(exc).__name__)
            if debug:
                raise
            return None

    async def run_turn(
        user_prompt: str,
        message_history: list[Any] | None,
    ) -> list[Any] | None:
        return await run_with_input({"input": user_prompt}, message_history)

    use_prompt_input = chat or initial_prompt is not None
    if use_prompt_input and not initial_prompt:
        emit_error("No input prompt provided", "ValueError")
        if render_task and not render_task.done():
            render_queue.put_nowait(None)
            render_closed = True
            await render_task
        return RunUiResult(result=None, exit_code=1)

    async def run_worker() -> int:
        nonlocal render_closed
        history: list[Any] | None
        if use_prompt_input:
            history = await run_with_input({"input": initial_prompt}, None)
        else:
            history = await run_with_input(input, None)
        if history is not None and app is not None:
            app.set_message_history(history)
        if not chat:
            render_queue.put_nowait(None)
            render_closed = True
        return exit_code

    app = LlmDoApp(
        tui_event_queue,
        approval_queue,
        worker_coro=run_worker(),
        run_turn=run_turn if chat else None,
        auto_quit=not chat,
    )

    await app.run_async(mouse=False)
    if not render_closed:
        render_queue.put_nowait(None)
        render_closed = True
    if not render_task.done():
        await render_task
    result = result_holder[0] if result_holder else None
    return RunUiResult(result=result, exit_code=exit_code)


async def run_headless(
    *,
    input: Any,
    entry: Entry | None = None,
    entry_factory: EntryFactory | None = None,
    project_root: Path | None = None,
    approval_mode: ApprovalMode = "approve_all",
    verbosity: int = 1,
    return_permission_errors: bool = True,
    max_depth: int = 5,
    worker_calls_require_approval: bool = False,
    worker_attachments_require_approval: bool = False,
    worker_approval_overrides: Mapping[str, Any] | None = None,
    backends: Sequence[DisplayBackend] | None = None,
    message_log_callback: MessageLogCallback | None = None,
    debug: bool = False,
    runtime_factory: RuntimeFactory | None = None,
    error_stream: TextIO | None = None,
) -> RunUiResult:
    """Run a single entry with a headless text backend."""
    entry_factory = _resolve_entry_factory(entry, entry_factory)
    if backends is None:
        backends = [HeadlessDisplayBackend(stream=sys.stderr, verbosity=verbosity)]
    render_task: asyncio.Task[None] | None = None
    render_queue: asyncio.Queue[UIEvent | None] | None = None
    on_event: RuntimeEventSink | None = None

    if backends:
        render_queue = asyncio.Queue()

        def on_event_callback(event: RuntimeEvent) -> None:
            render_queue.put_nowait(adapt_event(event))

        on_event = on_event_callback
        render_task = asyncio.create_task(_render_loop(render_queue, list(backends)))

    approval_policy = RunApprovalPolicy(
        mode=approval_mode,
        return_permission_errors=return_permission_errors,
    )

    runtime = _build_runtime(
        project_root=project_root,
        run_approval_policy=approval_policy,
        max_depth=max_depth,
        worker_calls_require_approval=worker_calls_require_approval,
        worker_attachments_require_approval=worker_attachments_require_approval,
        worker_approval_overrides=worker_approval_overrides,
        on_event=on_event,
        message_log_callback=message_log_callback,
        verbosity=verbosity,
        runtime_factory=runtime_factory,
    )

    result: Any | None = None
    exit_code = 0
    error_stream = error_stream or sys.stderr

    try:
        if approval_mode == "prompt":
            raise ValueError(
                "Headless mode cannot prompt for approvals; use approve_all or reject_all."
            )
        entry_instance = entry_factory()
        result, _ctx = await runtime.run_entry(entry_instance, input)
    except KeyboardInterrupt as exc:
        exit_code = 1
        print(f"\n{_format_run_error_message(exc)}", file=error_stream)
    except Exception as exc:
        exit_code = 1
        print(_format_run_error_message(exc), file=error_stream)
        if debug:
            raise
    finally:
        if render_queue is not None:
            render_queue.put_nowait(None)
            if render_task is not None and not render_task.done():
                await render_task

    return RunUiResult(result=result, exit_code=exit_code)


async def run_ui(
    *,
    input: Any,
    entry: Entry | None = None,
    entry_factory: EntryFactory | None = None,
    mode: UiMode = "tui",
    project_root: Path | None = None,
    approval_mode: ApprovalMode = "prompt",
    verbosity: int = 1,
    return_permission_errors: bool = True,
    max_depth: int = 5,
    worker_calls_require_approval: bool = False,
    worker_attachments_require_approval: bool = False,
    worker_approval_overrides: Mapping[str, Any] | None = None,
    backends: Sequence[DisplayBackend] | None = None,
    extra_backends: Sequence[DisplayBackend] | None = None,
    message_log_callback: MessageLogCallback | None = None,
    chat: bool = False,
    initial_prompt: str | None = None,
    debug: bool = False,
    worker_name: str | None = None,
    runtime_factory: RuntimeFactory | None = None,
    error_stream: TextIO | None = None,
) -> RunUiResult:
    """Run a single entry with either TUI or headless UI."""
    if mode == "tui":
        return await run_tui(
            input=input,
            entry=entry,
            entry_factory=entry_factory,
            project_root=project_root,
            approval_mode=approval_mode,
            verbosity=verbosity,
            return_permission_errors=return_permission_errors,
            max_depth=max_depth,
            worker_calls_require_approval=worker_calls_require_approval,
            worker_attachments_require_approval=worker_attachments_require_approval,
            worker_approval_overrides=worker_approval_overrides,
            message_log_callback=message_log_callback,
            extra_backends=extra_backends,
            chat=chat,
            initial_prompt=initial_prompt,
            debug=debug,
            worker_name=worker_name,
            runtime_factory=runtime_factory,
            error_stream=error_stream,
        )
    if mode == "headless":
        return await run_headless(
            input=input,
            entry=entry,
            entry_factory=entry_factory,
            project_root=project_root,
            approval_mode=approval_mode,
            verbosity=verbosity,
            return_permission_errors=return_permission_errors,
            max_depth=max_depth,
            worker_calls_require_approval=worker_calls_require_approval,
            worker_attachments_require_approval=worker_attachments_require_approval,
            worker_approval_overrides=worker_approval_overrides,
            backends=backends,
            message_log_callback=message_log_callback,
            debug=debug,
            runtime_factory=runtime_factory,
            error_stream=error_stream,
        )
    raise ValueError(f"Unknown UI mode: {mode}")
