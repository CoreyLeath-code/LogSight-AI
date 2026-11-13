# OpenTelemetry Collector and Trace–Log Correlation

## Reference pipeline

The enterprise Compose stack starts an OpenTelemetry Collector with OTLP/gRPC on
port 4317 and OTLP/HTTP on port 4318. Its reference configuration is
`deploy/otel/collector.yml`.

When `LOGSIGHT_OTEL_ENABLED=true`, the API creates an OTLP tracer provider and
exports bounded ingestion spans to the Collector. Every normalized event keeps an
existing `trace_id` and `span_id` parsed from the log line; if either value is
absent, the API fills it from the active ingestion span. The API response and the
recent-event endpoint therefore carry identifiers that can be joined to exported
traces.

## Local validation

```bash
docker compose -f docker-compose.enterprise.yml up --build
curl -sS http://localhost:8000/v1/logs \
  -H 'content-type: application/json' \
  -d '{"line":"ERROR checkout timeout","service":"checkout"}'
```

The response event contains 32-hex-character `trace_id` and 16-hex-character
`span_id` values. The Collector's `debug` exporter prints the matching span,
and Prometheus scrapes its own pipeline metrics on port 8888.

## Production promotion

The debug exporters intentionally do not persist telemetry. Before a production
deployment, replace them with authenticated, TLS-protected exporters to the
organization's trace, log, and metric backends. Restrict OTLP listeners to trusted
workloads, set exporter retry/queue limits for the expected load, and propagate
W3C trace context at ingress. Trace IDs are correlation identifiers, not secrets;
treat log payloads and resource attributes according to their data-classification
policy.
