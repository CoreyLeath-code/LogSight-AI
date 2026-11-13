"""Optional OpenTelemetry instrumentation and correlation helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .enterprise import EnrichedLog

try:
    from opentelemetry import trace
except ImportError:  # pragma: no cover
    trace = None  # type: ignore[assignment]


def configure_tracing(service_name: str) -> None:
    """Configure an OTLP tracer provider for an explicitly enabled deployment."""

    if trace is None:
        raise RuntimeError("Install the observability extra to enable OpenTelemetry tracing")
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        raise RuntimeError("Install the observability extra to enable OpenTelemetry tracing") from exc

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)


@contextmanager
def span(name: str, **attributes: str | int | float) -> Iterator[Any]:
    """Create an OTel span when installed, otherwise remain a no-op."""

    if trace is None:
        yield None
        return
    tracer = trace.get_tracer("logsight-ai")
    with tracer.start_as_current_span(name, attributes=attributes) as current:
        yield current


def correlate_with_active_span(event: EnrichedLog) -> EnrichedLog:
    """Fill missing event correlation fields from the current valid OTel span."""

    if trace is None:
        return event
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return event
    if event.trace_id is None:
        event.trace_id = f"{context.trace_id:032x}"
    if event.span_id is None:
        event.span_id = f"{context.span_id:016x}"
    return event
