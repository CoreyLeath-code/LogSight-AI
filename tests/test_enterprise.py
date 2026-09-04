"""Tests for enterprise observability primitives."""

from logsight.enterprise import (
    WebhookNotifier,
    enrich,
    extract_template,
    score_event,
    semantic_features,
)
from logsight.parser import parse_line


def test_enriched_event_contains_correlation_fields() -> None:
    entry = parse_line("2026-09-04T12:00:00Z ERROR api: database timeout trace_id=abc span_id=def")
    event = enrich(entry, service="payments", source="kubernetes", host="node-1")
    assert event.service == "payments"
    assert event.source == "kubernetes"
    assert event.host == "node-1"
    assert event.fingerprint
    assert event.to_dict()["level"] == "ERROR"
    assert '"payments"' in event.to_json()


def test_template_extraction_and_features_are_deterministic() -> None:
    assert extract_template("request failed after 42 ms") == "request failed after <*> ms"
    assert semantic_features("Database Timeout") == semantic_features("database timeout")
    assert len(semantic_features("hello world")) == 32


def test_hybrid_score_is_bounded() -> None:
    event = enrich(parse_line("ERROR database connection failed"), service="db")
    event.template = extract_template(event.message)
    result = score_event(event, [event])
    assert 0.0 <= result.score <= 1.0
    assert result.detector == "hybrid"


def test_webhook_without_url_is_safe() -> None:
    assert WebhookNotifier(url=None).send({"severity": "high"}) is False
