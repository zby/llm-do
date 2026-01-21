from __future__ import annotations

from collections.abc import AsyncIterable, Callable
from typing import Any

from pydantic_ai import RunContext


def event_stream_logger(prefix: str = "") -> Callable[[RunContext[Any], AsyncIterable[Any]], Any]:
    async def handler(_: RunContext[Any], events: AsyncIterable[Any]) -> None:
        async for event in events:
            print(f"{prefix}{type(event).__name__}: {event}")

    return handler
