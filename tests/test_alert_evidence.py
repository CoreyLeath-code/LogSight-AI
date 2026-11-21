"""Synthetic alert evidence regression tests; no alert is fired."""

from __future__ import annotations

import pytest

from logsight.alert_evidence import assess_alert_delivery


def sample() -> dict[str, object]:
    return {
        "environment": "isolated-staging",
        "operator": "operator",
        "reviewer": "reviewer",
        "approval_ticket": "CHANGE-123",
        "git_revision": "a" * 40,
        "image_digest": "sha256:" + "a" * 64,
        "alert_name": "LogSightKafkaReadinessFailuresObserved",
        "receiver_reference": "restricted-receiver-id",
        "source_observed": True,
        "alert_fired": True,
        "receiver_delivered": True,
        "operator_acknowledged": True,
        "signal_at_utc": "2026-11-20T10:00:00Z",
        "fired_at_utc": "2026-11-20T10:01:00Z",
        "delivered_at_utc": "2026-11-20T10:01:10Z",
        "acknowledged_at_utc": "2026-11-20T10:02:00Z",
        "approved_max_ack_seconds": 180,
        "evidence_links": ["https://example.invalid/restricted-evidence"],
    }


def test_synthetic_acknowledgment_under_approved_limit() -> None:
    assert assess_alert_delivery(sample()) == {
        "status": "pass",
        "signal_to_ack_seconds": 120.0,
        "meets_approved_ack_window": True,
    }


def test_delayed_acknowledgment_fails_objective() -> None:
    record = sample()
    record["approved_max_ack_seconds"] = 60
    assert assess_alert_delivery(record)["status"] == "fail"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("environment", "production"),
        ("source_observed", False),
        ("alert_fired", False),
        ("receiver_delivered", False),
        ("operator_acknowledged", False),
        ("approved_max_ack_seconds", 0),
        ("approved_max_ack_seconds", True),
        ("evidence_links", []),
        ("evidence_links", ["http://example.invalid/evidence"]),
        ("fired_at_utc", "2026-11-20T09:59:00Z"),
        ("delivered_at_utc", "2026-11-20T10:00:30Z"),
        ("acknowledged_at_utc", "2026-11-20T10:01:00"),
        ("reviewer", ""),
    ],
)
def test_invalid_or_unconfirmed_alert_evidence_rejected(field: str, value: object) -> None:
    record = sample()
    record[field] = value
    with pytest.raises(ValueError):
        assess_alert_delivery(record)


def test_missing_field_rejected() -> None:
    record = sample()
    del record["receiver_reference"]
    with pytest.raises(ValueError, match="receiver_reference"):
        assess_alert_delivery(record)
