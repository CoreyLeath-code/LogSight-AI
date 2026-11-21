"""Static checks for example Phase 4 readiness alert rules."""

from __future__ import annotations

from pathlib import Path

import yaml

RULES = Path(__file__).resolve().parents[1] / "deploy/prometheus/logsight-readiness-alerts.yaml"


def test_alert_rules_are_parseable_and_use_existing_fixed_metrics() -> None:
    data = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    groups = data["groups"]
    assert len(groups) == 1
    rules = groups[0]["rules"]
    assert {rule["alert"] for rule in rules} == {
        "LogSightKafkaReadinessFailuresObserved",
        "LogSightRedisReadinessFailuresObserved",
    }
    metrics = {
        "logsight_readiness_kafka_failure_total",
        "logsight_readiness_redis_failure_total",
    }
    for rule in rules:
        expression = rule["expr"]
        assert any(name in expression for name in metrics)
        assert "increase(" in expression
        assert "sum by (job)" in expression
        assert rule["for"] == "2m"
        assert rule["labels"]["severity"] == "warning"
        assert rule["annotations"]["runbook_url"].endswith(
            "/docs/PHASE4_ALERT_RESPONSE.md"
        )


def test_example_rules_have_no_sensitive_or_high_cardinality_labels() -> None:
    data = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    for rule in data["groups"][0]["rules"]:
        assert set(rule["labels"]) == {"severity"}
        assert "by (job)" in rule["expr"]
        assert all(
            token not in rule["expr"]
            for token in ("tenant", "event_id", "topic", "raw", "message", "password")
        )
