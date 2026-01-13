"""Display backend abstractions for the async CLI.

With events knowing how to render themselves, backends become thin wrappers
that simply call the appropriate render method on each event.
"""
from __future__ import annotations

import asyncio
import sys
from abc import ABC, abstractmethod
from typing import TextIO

from .events import UIEvent


class DisplayBackend(ABC):
    """Interface for rendering UI events."""

    verbosity: int = 0

    async def start(self) -> None:
        """Called before event loop starts."""
        pass

    async def stop(self) -> None:
        """Called after event loop ends."""
        pass

    @abstractmethod
    def display(self, event: UIEvent) -> None:
        """Display a single typed event."""
        ...


class RichDisplayBackend(DisplayBackend):
    """Rich-formatted renderer using Rich Console.

    Verbosity levels:
        0 - Minimal: Only show prompts, responses, tool calls/results, status
        1 - Normal: Add progress indicators (Generating..., Complete)
        2 - Verbose: Add streaming deltas (partial responses as they arrive)
    """

    def __init__(
        self,
        stream: TextIO | None = None,
        force_terminal: bool = False,
        verbosity: int = 0,
    ):
        from rich.console import Console

        self.stream = stream or sys.stderr
        self.verbosity = verbosity
        self.console = Console(
            file=self.stream,
            force_terminal=force_terminal,
            width=120,
        )

    def display(self, event: UIEvent) -> None:
        renderable = event.render_rich(self.verbosity)
        if renderable is not None:
            from .events import TextResponseEvent

            if isinstance(event, TextResponseEvent) and event.is_delta:
                self.console.print(renderable, end="")
            else:
                self.console.print(renderable)


class HeadlessDisplayBackend(DisplayBackend):
    """Plain text renderer (ASCII only, no ANSI codes).

    Verbosity levels:
        0 - Minimal: Only show prompts, responses, tool calls/results, status
        1 - Normal: Add progress indicators (Generating..., Complete)
        2 - Verbose: Add streaming deltas (partial responses as they arrive)
    """

    def __init__(self, stream: TextIO | None = None, verbosity: int = 0):
        self.stream = stream or sys.stderr
        self.verbosity = verbosity

    def display(self, event: UIEvent) -> None:
        text = event.render_text(self.verbosity)
        if text is not None:
            from .events import TextResponseEvent

            if isinstance(event, TextResponseEvent) and event.is_delta:
                self.stream.write(text)
            else:
                self.stream.write(text + "\n")
            self.stream.flush()


class TextualDisplayBackend(DisplayBackend):
    """Forwards events to Textual TUI app via queue."""

    def __init__(self, event_queue: asyncio.Queue[UIEvent | None]):
        self._queue = event_queue

    def display(self, event: UIEvent) -> None:
        self._queue.put_nowait(event)
