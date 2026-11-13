"""Contract checks for the OpenTelemetry Collector reference deployment."""

from pathlib import Path

from logsight.enterprise import enrich
from logsight.observability import correlate_with_active_span
from logsight.parser import parse_line


def test_collector_configuration_exposes_otlp_signal_pipelines() -> None:
    configuration = Path("deploy/otel/collector.yml").read_text(encoding="utf-8")

    assert "grpc:" in configuration
    assert "http:" in configuration
    assert "traces:" in configuration
    assert "logs:" in configuration
    assert "spanmetrics:" in configuration
    assert "memory_limiter" in configuration


def test_correlation_never_overwrites_log_supplied_identifiers() -> None:
    event = enrich(parse_line("ERROR request failed"))
    event.trace_id = "upstream"
    event.span_id = "child"

    correlated = correlate_with_active_span(event)

    assert correlated.trace_id == "upstream"
    assert correlated.span_id == "child"
