"""Optional OpenTelemetry instrumentation helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

try:
    from opentelemetry import trace
except ImportError:  # pragma: no cover
    trace = None  # type: ignore[assignment]


@contextmanager
def span(name: str, **attributes: str | int | float) -> Iterator[Any]:
    """Create an OTel span when installed, otherwise remain a no-op."""
    if trace is None:
        yield None
        return
    tracer = trace.get_tracer("logsight-ai")
    with tracer.start_as_current_span(name, attributes=attributes) as current:
        yield current
