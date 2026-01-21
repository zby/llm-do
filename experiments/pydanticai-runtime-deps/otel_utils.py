from __future__ import annotations

import atexit
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from pydantic_ai import InstrumentationSettings


@dataclass(frozen=True)
class TraceConfig:
    settings: InstrumentationSettings
    path: Path


class JsonlSpanExporter(SpanExporter):
    def __init__(self, path: Path) -> None:
        self._path = path
        self._file = path.open("a", encoding="utf-8")
        self._lock = threading.Lock()

    def export(self, spans: Iterable[ReadableSpan]) -> SpanExportResult:
        with self._lock:
            for span in spans:
                self._file.write(span.to_json(indent=None))
                self._file.write("\n")
            self._file.flush()
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        with self._lock:
            self._file.flush()
        return True

    def shutdown(self) -> None:
        with self._lock:
            self._file.close()


def configure_trace_logging(
    trace_dir: Path,
    *,
    run_name: str,
    include_content: bool = True,
    include_binary_content: bool = False,
) -> TraceConfig:
    trace_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    file_path = trace_dir / f"{run_name}-{timestamp}-{os.getpid()}.jsonl"

    exporter = JsonlSpanExporter(file_path)
    resource = Resource.create(
        {
            "service.name": "pydanticai-experiment",
            "llm_do.experiment": run_name,
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    atexit.register(tracer_provider.shutdown)

    settings = InstrumentationSettings(
        tracer_provider=tracer_provider,
        include_content=include_content,
        include_binary_content=include_binary_content,
    )
    return TraceConfig(settings=settings, path=file_path)
